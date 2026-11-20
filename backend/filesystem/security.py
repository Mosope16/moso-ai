"""
Moso AI — Filesystem Security & Access Boundary
Enforces strict path confinement within the user's home directory, canonical resolution,
symlink validation, traversal blocking, sensitive file protection, and autonomy policy.
"""

import os
import re
from pathlib import Path
from typing import Tuple, Optional, Set, List, Dict, Any


def get_home_directory() -> Path:
    """
    Dynamically resolve the user's real home directory on Arch Linux.
    Never hardcodes a specific username.
    """
    return Path.home().resolve()


# Sensitive relative paths and patterns under home directory
SENSITIVE_DIRECTORIES: Set[str] = {
    ".ssh",
    ".gnupg",
    ".aws",
    ".config/credentials",
    ".config/google-chrome",
    ".config/BraveSoftware",
    ".config/chromium",
    ".mozilla",
    ".local/share/keyrings",
    ".pki",
    ".password-store",
}

SENSITIVE_FILES: Set[str] = {
    ".env",
    ".bashrc",
    ".zshrc",
    ".profile",
    ".bash_profile",
    ".bash_login",
    ".bash_logout",
    ".bash_history",
    ".zsh_history",
    ".git-credentials",
    ".netrc",
}

# Regex to catch dangerous secret file patterns anywhere
SECRET_PATTERN = re.compile(
    r'(^|/)(\.env(\.[a-zA-Z0-9_\-]+)?|id_rsa|id_ed25519|id_ecdsa|.*\.pem|.*\.key|.*\.kdbx)$',
    re.IGNORECASE
)


class PathSecurityException(Exception):
    """Raised when a path violates safety policies."""
    pass


def resolve_safe_path(user_path: str, base_dir: Optional[Path] = None) -> Path:
    """
    Converts a user-supplied or model-supplied path into a canonical Path,
    resolving '~' to the user's home directory.
    Validates that:
    1. The path does not contain illegal characters or null bytes.
    2. Path stays strictly within the base_dir (default: user's home).
    3. Symlinks are resolved and must point within the base_dir.
    4. Special device files (/dev, sockets, fifos) are rejected.
    """
    if not user_path or not user_path.strip():
        raise PathSecurityException("Path cannot be empty.")

    cleaned = user_path.strip()

    # Reject null bytes
    if "\0" in cleaned:
        raise PathSecurityException("Null bytes in path are forbidden.")

    home = base_dir.resolve() if base_dir else get_home_directory()

    # Expand ~ or handle relative paths
    if cleaned == "~" or cleaned.startswith("~/"):
        resolved_input = home / cleaned[2:] if cleaned.startswith("~/") else home
    elif os.path.isabs(cleaned):
        resolved_input = Path(cleaned)
    else:
        # Relative path is resolved against home or base_dir
        resolved_input = home / cleaned

    try:
        # Resolve canonical path (follows symlinks)
        canonical = resolved_input.resolve()
    except Exception as e:
        raise PathSecurityException(f"Failed to resolve path '{user_path}': {str(e)}")

    # Strict confinement check: canonical path must start with home directory path
    try:
        canonical.relative_to(home)
    except ValueError:
        raise PathSecurityException(
            f"Path escape detected: '{user_path}' resolves outside the allowed home directory ({home})."
        )

    # Reject special device files, sockets, fifos
    if canonical.exists():
        if canonical.is_char_device() or canonical.is_block_device() or canonical.is_fifo() or canonical.is_socket():
            raise PathSecurityException(f"Access to special device nodes or sockets is prohibited: '{canonical}'.")

    return canonical


def is_sensitive_path(path: Path, home: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Checks if a canonical path belongs to sensitive directories, credential stores,
    shell configuration, or encryption keys.
    Returns (is_sensitive: bool, reason: str).
    """
    home_dir = home or get_home_directory()
    try:
        rel_str = str(path.relative_to(home_dir))
    except ValueError:
        return True, "Path is outside the user home directory."

    parts = path.parts
    # Check sensitive directories
    for sensitive_dir in SENSITIVE_DIRECTORIES:
        sens_parts = tuple(sensitive_dir.split("/"))
        # Check if sensitive directory is part of the path hierarchy
        for i in range(len(parts) - len(sens_parts) + 1):
            if parts[i:i + len(sens_parts)] == sens_parts:
                return True, f"Located inside protected security directory '~/{sensitive_dir}'"

    # Check sensitive files
    if path.name in SENSITIVE_FILES or SECRET_PATTERN.search(rel_str):
        return True, f"Protected configuration/secret file: '{path.name}'"

    return False, ""


# Autonomy Policy: Category A, B, and C
CATEGORY_AUTO_PERMITTED = "A"          # Discovery, reading non-sensitive, safe inspection
CATEGORY_CHANGE_TRACKING = "B"         # Editing, moving, renaming, copying with backups & undo
CATEGORY_REQUIRE_APPROVAL = "C"        # Deleting, sensitive files, destructive commands


def classify_operation_autonomy(
    action: str,
    target_path: Optional[Path] = None,
    params: Optional[Dict[str, Any]] = None,
    home: Optional[Path] = None
) -> Tuple[str, bool, str, str]:
    """
    Evaluates an operation under Moso AI's Balanced Autonomy Policy.
    Returns:
        (category: "A"|"B"|"C", requires_approval: bool, risk_level: str, explanation: str)
    """
    home_dir = home or get_home_directory()

    # 1. Check path sensitivity
    if target_path:
        is_sens, sens_reason = is_sensitive_path(target_path, home_dir)
        if is_sens:
            # Sensitive files ALWAYS require explicit approval regardless of action
            return (
                CATEGORY_REQUIRE_APPROVAL,
                True,
                "critical",
                f"Operation '{action}' targets a sensitive path: {sens_reason}. Explicit user approval is mandatory."
            )

    # 2. Deletions always require approval
    if action in ("delete_file", "delete_directory", "remove_file", "unlink", "rmdir"):
        return (
            CATEGORY_REQUIRE_APPROVAL,
            True,
            "high",
            f"Deleting '{target_path.name if target_path else 'item'}' is a destructive action requiring explicit approval."
        )

    # 3. Read & Discovery Operations (Category A - Auto Permitted)
    if action in (
        "list_directory",
        "get_file_info",
        "search_files",
        "search_file_contents",
        "find_duplicate_files",
        "get_directory_size",
        "read_file",
        "read_file_range",
        "read_document",
        "read_image_metadata",
        "create_backup",
        "get_operation_history",
    ):
        return (CATEGORY_AUTO_PERMITTED, False, "low", "Read-only inspection operation.")

    # 4. Folder Creation & Non-sensitive New File Creation (Category A - Auto Permitted)
    if action == "create_directory":
        return (CATEGORY_AUTO_PERMITTED, False, "low", "Creating directory.")

    if action == "create_file":
        if target_path and target_path.exists():
            # Overwriting an existing file transitions to Category B (requires change tracking & backup)
            return (
                CATEGORY_CHANGE_TRACKING,
                False,
                "medium",
                f"Modifying existing file '{target_path.name}' — automatic backup will be created."
            )
        return (CATEGORY_AUTO_PERMITTED, False, "low", "Creating new file.")

    # 5. File Modifications & Organization (Category B - Execute with Change Tracking & Backup)
    if action in ("edit_file", "apply_file_patch", "rename_file", "move_file", "copy_file", "undo_operation"):
        return (
            CATEGORY_CHANGE_TRACKING,
            False,
            "medium",
            f"Operation '{action}' modifies file system state. Reversible backup and tracking enforced."
        )

    # 6. Terminal Commands
    if action == "run_terminal_command":
        from .sandbox import is_terminal_command_allowlisted
        cmd = (params or {}).get("command", "")
        args = (params or {}).get("args", [])
        is_safe, risk_level, reason = is_terminal_command_allowlisted(cmd, args)
        if is_safe:
            return (CATEGORY_AUTO_PERMITTED, False, risk_level, reason)
        else:
            return (CATEGORY_REQUIRE_APPROVAL, True, risk_level, reason)

    # Default fallback for unknown actions: Require approval
    return (
        CATEGORY_REQUIRE_APPROVAL,
        True,
        "high",
        f"Unknown or unclassified filesystem action: '{action}'. Requires user approval."
    )
