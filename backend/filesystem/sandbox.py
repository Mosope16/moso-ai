"""
Moso AI — Linux Bubblewrap Sandbox & Restricted Terminal Execution
Executes permitted terminal commands within unprivileged Linux namespaces using Bubblewrap.
Enforces strict command allowlisting, argument validation, and masks sensitive user files.
"""

import os
import shutil
import asyncio
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional
from .security import get_home_directory, resolve_safe_path, is_sensitive_path

# Path to system bubblewrap on Arch Linux
BWRAP_BINARY = "/usr/bin/bwrap" if os.path.exists("/usr/bin/bwrap") else shutil.which("bwrap")

# Explicit safe command allowlist with permitted flags/subcommands
SAFE_COMMAND_ALLOWLIST = {
    "pwd": {"max_args": 0},
    "ls": {"max_args": 5, "allowed_flags": {"-l", "-a", "-la", "-lh", "-h", "-t", "-r", "--color=auto"}},
    "stat": {"max_args": 3},
    "file": {"max_args": 3},
    "du": {"max_args": 4, "allowed_flags": {"-s", "-h", "-sh", "-d", "--max-depth=1", "--max-depth=2"}},
    "df": {"max_args": 3, "allowed_flags": {"-h", "-k", "-m", "-T"}},
    "find": {"max_args": 8, "disallowed_tokens": {"-exec", "-execdir", "-delete", "-ok", "-okdir"}},
    "git": {
        "allowed_subcommands": {"status", "log", "diff", "branch", "show", "rev-parse"},
        "max_args": 10,
    },
    "python": {"allowed_exact": [["--version"], ["-V"]]},
    "python3": {"allowed_exact": [["--version"], ["-V"]]},
    "node": {"allowed_exact": [["--version"], ["-v"]]},
    "npm": {"allowed_exact": [["test"], ["run", "test"], ["--version"], ["-v"]]},
    "pytest": {"max_args": 6},
    "ollama": {"allowed_subcommands": {"list", "ps"}},
}

# Strictly forbidden commands that cannot be auto-executed under any circumstances
DANGEROUS_COMMANDS = {
    "rm", "rmdir", "sudo", "su", "chmod", "chown", "chgrp",
    "dd", "mkfs", "fdisk", "parted", "systemctl", "journalctl",
    "pacman", "yay", "paru", "makepkg", "kill", "pkill", "killall",
    "shutdown", "reboot", "poweroff", "curl", "wget", "nc", "ncat", "netcat",
    "ssh", "scp", "sftp", "gpg", "sh", "bash", "zsh", "fish",
}


def is_terminal_command_allowlisted(command: str, args: Optional[List[str]] = None) -> Tuple[bool, str, str]:
    """
    Validates whether a proposed command matches the strict safe inspection allowlist.
    Returns:
        (is_allowlisted: bool, risk_level: str, reason: str)
    """
    cmd = (command or "").strip()
    cmd_args = args or []

    if not cmd:
        return False, "critical", "Empty command."

    # Extract base command name
    base_cmd = Path(cmd).name.lower()

    if base_cmd in DANGEROUS_COMMANDS:
        return False, "critical", f"Command '{base_cmd}' is in the forbidden/destructive system operations list."

    if base_cmd not in SAFE_COMMAND_ALLOWLIST:
        return False, "high", f"Command '{base_cmd}' is not in the pre-approved safe inspection allowlist."

    rule = SAFE_COMMAND_ALLOWLIST[base_cmd]

    # Check exact matching rules
    if "allowed_exact" in rule:
        matches_exact = any(cmd_args == exact for exact in rule["allowed_exact"])
        if matches_exact:
            return True, "low", f"Safe inspection query: {base_cmd} {' '.join(cmd_args)}"
        return False, "medium", f"Arguments for '{base_cmd}' are not in the permitted safe options."

    # Check git subcommands
    if base_cmd == "git":
        if not cmd_args:
            return False, "medium", "Git requires a read-only subcommand."
        sub = cmd_args[0].lower()
        if sub in rule.get("allowed_subcommands", set()):
            # Disallow writing subcommands or hooks
            for arg in cmd_args[1:]:
                if arg.startswith("--output") or arg in ("-i", "--interactive"):
                    return False, "high", "Interactive or write options are prohibited in safe mode."
            return True, "low", f"Safe Git inspection: git {sub}"
        return False, "high", f"Git subcommand '{sub}' requires explicit approval."

    # Check ollama subcommands
    if base_cmd == "ollama":
        if cmd_args and cmd_args[0].lower() in rule.get("allowed_subcommands", set()):
            return True, "low", f"Safe Ollama status query: ollama {cmd_args[0]}"
        return False, "medium", "Ollama subcommand requires explicit approval."

    # Check find command arguments
    if base_cmd == "find":
        disallowed = rule.get("disallowed_tokens", set())
        for arg in cmd_args:
            if arg.lower() in disallowed:
                return False, "critical", f"Find argument '{arg}' could execute arbitrary code or delete files."
        return True, "low", "Safe filesystem find query."

    # General arg limits
    max_args = rule.get("max_args", 10)
    if len(cmd_args) > max_args:
        return False, "medium", f"Too many arguments for '{base_cmd}' (max {max_args})."

    return True, "low", f"Safe inspection command: {base_cmd}"


class BwrapSandbox:
    """
    Encapsulates execution of terminal commands inside Arch Linux Bubblewrap namespaces.
    """

    def __init__(self, allowed_work_dir: Optional[Path] = None):
        self.home = get_home_directory()
        self.allowed_work_dir = (allowed_work_dir or self.home).resolve()
        self.bwrap_available = bool(BWRAP_BINARY and os.path.exists(BWRAP_BINARY))

    def build_bwrap_argv(self, cmd_argv: List[str], cwd: Path, read_only: bool = True) -> List[str]:
        """
        Constructs the bubblewrap command-line arguments to isolate execution.
        """
        bwrap_args = [
            BWRAP_BINARY,
            # Read-only root filesystem
            "--ro-bind", "/", "/",
            # Virtual device and process filesystem
            "--dev", "/dev",
            "--proc", "/proc",
            # Isolated temp filesystem
            "--tmpfs", "/tmp",
            # Mask sensitive secret directories under user home with empty tmpfs
            "--tmpfs", str(self.home / ".ssh"),
            "--tmpfs", str(self.home / ".gnupg"),
            "--tmpfs", str(self.home / ".aws"),
            "--tmpfs", str(self.home / ".config" / "google-chrome"),
            "--tmpfs", str(self.home / ".config" / "BraveSoftware"),
            "--tmpfs", str(self.home / ".mozilla"),
            # Unshare all namespaces (network, IPC, PID, UTS)
            "--unshare-all",
            "--die-with-parent",
        ]

        # Bind working directory: read-only by default, or read-write if explicitly granted
        cwd_str = str(cwd.resolve())
        if not read_only:
            bwrap_args.extend(["--bind", cwd_str, cwd_str])
        else:
            bwrap_args.extend(["--ro-bind", cwd_str, cwd_str])

        bwrap_args.extend(["--chdir", cwd_str])
        bwrap_args.extend(cmd_argv)
        return bwrap_args

    async def execute_command(
        self,
        command: str,
        args: Optional[List[str]] = None,
        cwd: Optional[Path] = None,
        read_only: bool = True,
        timeout_seconds: float = 20.0
    ) -> Dict[str, Any]:
        """
        Executes a validated command inside the sandbox without shell=True.
        """
        work_dir = resolve_safe_path(str(cwd)) if cwd else self.allowed_work_dir
        cmd_argv = [command] + (args or [])

        # Sanitize environment variables (remove tokens, keys, passwords)
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": str(self.home),
            "USER": os.environ.get("USER", "sope"),
            "TERM": "xterm-256color",
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        }

        use_bwrap = self.bwrap_available

        if use_bwrap:
            full_argv = self.build_bwrap_argv(cmd_argv, work_dir, read_only=read_only)
        else:
            full_argv = cmd_argv

        try:
            proc = await asyncio.create_subprocess_exec(
                *full_argv,
                cwd=str(work_dir) if not use_bwrap else None,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
                return {
                    "success": False,
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout_seconds}s.",
                    "sandboxed": use_bwrap,
                    "timed_out": True,
                }

            stdout_str = stdout_bytes.decode("utf-8", errors="replace")
            stderr_str = stderr_bytes.decode("utf-8", errors="replace")

            # Limit output length to prevent context explosion (max 10,000 characters)
            if len(stdout_str) > 10000:
                stdout_str = stdout_str[:10000] + f"\n... [Output truncated: {len(stdout_str) - 10000} characters omitted]"
            if len(stderr_str) > 5000:
                stderr_str = stderr_str[:5000] + f"\n... [Error output truncated]"

            return {
                "success": (proc.returncode == 0),
                "exit_code": proc.returncode,
                "stdout": stdout_str,
                "stderr": stderr_str,
                "sandboxed": use_bwrap,
                "timed_out": False,
            }

        except Exception as e:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "sandboxed": use_bwrap,
                "timed_out": False,
            }
