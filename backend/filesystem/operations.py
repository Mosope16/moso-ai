"""
Moso AI — Core Filesystem Operations Engine
Implements discovery, reading, writing, atomic editing, duplicate detection,
and terminal execution with permission enforcement and backup tracking.
"""

import os
import difflib
import hashlib
import fnmatch
from pathlib import Path
from typing import Dict, Any, List, Optional
from .security import (
    get_home_directory,
    resolve_safe_path,
    is_sensitive_path,
    classify_operation_autonomy,
    CATEGORY_REQUIRE_APPROVAL,
    PathSecurityException,
)
from .documents import (
    read_text_file_safe,
    read_file_line_range,
    extract_pdf_document,
    extract_docx_document,
    extract_xlsx_document,
    extract_csv_document,
    inspect_image_metadata,
)
from .history import (
    create_file_backup,
    calculate_sha256,
    record_operation,
)
from .sandbox import BwrapSandbox, is_terminal_command_allowlisted


# -------------------------------------------------------------
# 1. Discovery Operations
# -------------------------------------------------------------

def list_directory(
    path: str = "~",
    recursive: bool = False,
    max_depth: int = 2,
    include_hidden: bool = False,
    max_entries: int = 150
) -> Dict[str, Any]:
    """
    Lists directory contents with file types, sizes, and timestamps.
    """
    try:
        canonical = resolve_safe_path(path)
        if not canonical.is_dir():
            return {"success": False, "error": f"Path is not a directory: '{path}'"}

        entries = []
        truncated = False

        if not recursive:
            with os.scandir(canonical) as it:
                for entry in it:
                    if not include_hidden and entry.name.startswith("."):
                        continue
                    try:
                        stat = entry.stat()
                        is_dir = entry.is_dir(follow_symlinks=False)
                        size_kb = f"{stat.st_size / 1024:.1f} KB" if not is_dir else "-"
                        entries.append({
                            "name": entry.name,
                            "type": "directory" if is_dir else "file",
                            "size": size_kb,
                            "bytes": stat.st_size if not is_dir else 0,
                            "modified_at": stat.st_mtime,
                        })
                    except Exception:
                        continue
                    if len(entries) >= max_entries:
                        truncated = True
                        break
        else:
            base_depth = len(canonical.parts)
            for root, dirs, files in os.walk(canonical):
                curr_depth = len(Path(root).parts) - base_depth
                if curr_depth > max_depth:
                    continue

                if not include_hidden:
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                    files = [f for f in files if not f.startswith(".")]

                for f in files:
                    try:
                        p = Path(root) / f
                        stat = p.stat()
                        entries.append({
                            "name": str(p.relative_to(canonical)),
                            "type": "file",
                            "size": f"{stat.st_size / 1024:.1f} KB",
                            "bytes": stat.st_size,
                        })
                    except Exception:
                        pass
                    if len(entries) >= max_entries:
                        truncated = True
                        break
                if truncated:
                    break

        # Sort: directories first, then alphabetical
        entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"].lower()))

        return {
            "success": True,
            "path": str(canonical),
            "total_found": len(entries),
            "entries": entries,
            "truncated": truncated,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_file_info(path: str) -> Dict[str, Any]:
    """
    Returns detailed file metadata (size, permissions, timestamps, MIME/extension).
    """
    try:
        canonical = resolve_safe_path(path)
        if not canonical.exists():
            return {"success": False, "error": f"Path does not exist: '{path}'"}

        stat = canonical.stat()
        is_dir = canonical.is_dir()
        size_bytes = stat.st_size
        size_str = (
            f"{size_bytes / (1024 * 1024):.2f} MB" if size_bytes >= 1024 * 1024
            else f"{size_bytes / 1024:.1f} KB"
        ) if not is_dir else "directory"

        is_sens, sens_reason = is_sensitive_path(canonical)

        return {
            "success": True,
            "path": str(canonical),
            "name": canonical.name,
            "extension": canonical.suffix.lower(),
            "is_directory": is_dir,
            "size": size_str,
            "bytes": size_bytes,
            "created_at": stat.st_ctime,
            "modified_at": stat.st_mtime,
            "is_sensitive": is_sens,
            "sensitivity_reason": sens_reason if is_sens else None,
            "sha256": calculate_sha256(canonical) if not is_dir and size_bytes < 50 * 1024 * 1024 else None,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def search_files(
    pattern: str,
    path: str = "~",
    max_results: int = 50,
    include_hidden: bool = False
) -> Dict[str, Any]:
    """
    Searches for files matching a glob or substring pattern (e.g., '*.pdf', 'report*').
    """
    try:
        canonical = resolve_safe_path(path)
        if not canonical.is_dir():
            return {"success": False, "error": f"Base path is not a directory: '{path}'"}

        matched = []
        truncated = False
        glob_pat = pattern if any(c in pattern for c in "*?[]") else f"*{pattern}*"

        for root, dirs, files in os.walk(canonical):
            if not include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                files = [f for f in files if not f.startswith(".")]

            for f in files:
                if fnmatch.fnmatch(f.lower(), glob_pat.lower()):
                    full_p = Path(root) / f
                    try:
                        stat = full_p.stat()
                        matched.append({
                            "path": str(full_p),
                            "name": f,
                            "size": f"{stat.st_size / 1024:.1f} KB",
                            "bytes": stat.st_size,
                            "modified_at": stat.st_mtime,
                        })
                    except Exception:
                        pass
                if len(matched) >= max_results:
                    truncated = True
                    break
            if truncated:
                break

        return {
            "success": True,
            "query": pattern,
            "searched_in": str(canonical),
            "matches_count": len(matched),
            "matches": matched,
            "truncated": truncated,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def search_file_contents(
    query: str,
    path: str = "~",
    file_extensions: Optional[List[str]] = None,
    max_results: int = 30
) -> Dict[str, Any]:
    """
    Grep-like text search across files in a directory.
    """
    try:
        canonical = resolve_safe_path(path)
        if not canonical.is_dir():
            return {"success": False, "error": f"Base path is not a directory: '{path}'"}

        exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in file_extensions} if file_extensions else None
        matches = []
        q_lower = query.lower()

        for root, dirs, files in os.walk(canonical):
            # Skip hidden and cache folders
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", ".git", "__pycache__", "target", "build", "dist")]

            for f in files:
                if f.startswith("."):
                    continue
                ext = Path(f).suffix.lower()
                if exts and ext not in exts:
                    continue

                full_p = Path(root) / f
                try:
                    stat = full_p.stat()
                    # Skip huge files (> 2MB for content grep)
                    if stat.st_size > 2 * 1024 * 1024:
                        continue

                    with open(full_p, "r", encoding="utf-8", errors="ignore") as file_obj:
                        for l_idx, line in enumerate(file_obj, start=1):
                            if q_lower in line.lower():
                                matches.append({
                                    "file": str(full_p),
                                    "line_number": l_idx,
                                    "line_snippet": line.strip()[:200],
                                })
                                if len(matches) >= max_results:
                                    break
                except Exception:
                    pass
                if len(matches) >= max_results:
                    break
            if len(matches) >= max_results:
                break

        return {
            "success": True,
            "query": query,
            "matches_count": len(matches),
            "matches": matches,
            "truncated": len(matches) >= max_results,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def find_duplicate_files(
    directory_path: str = "~",
    min_size_bytes: int = 1024,
    max_files_to_scan: int = 1000
) -> Dict[str, Any]:
    """
    Finds duplicate files based on size and SHA-256 hash.
    Does not delete anything automatically.
    """
    try:
        canonical = resolve_safe_path(directory_path)
        if not canonical.is_dir():
            return {"success": False, "error": f"Path is not a directory: '{directory_path}'"}

        size_map: Dict[int, List[Path]] = {}
        scanned_count = 0

        for root, dirs, files in os.walk(canonical):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", ".git")]
            for f in files:
                if f.startswith("."):
                    continue
                p = Path(root) / f
                try:
                    s = p.stat().st_size
                    if s >= min_size_bytes:
                        size_map.setdefault(s, []).append(p)
                        scanned_count += 1
                except Exception:
                    pass
                if scanned_count >= max_files_to_scan:
                    break
            if scanned_count >= max_files_to_scan:
                break

        # Filter potential duplicates by hash
        duplicates: List[Dict[str, Any]] = []
        for size, path_list in size_map.items():
            if len(path_list) > 1:
                hash_submap: Dict[str, List[str]] = {}
                for p in path_list:
                    h = calculate_sha256(p)
                    if h:
                        hash_submap.setdefault(h, []).append(str(p))
                for h, matched_paths in hash_submap.items():
                    if len(matched_paths) > 1:
                        duplicates.append({
                            "sha256": h,
                            "size_bytes": size,
                            "size_human": f"{size / 1024:.1f} KB",
                            "paths": matched_paths,
                            "count": len(matched_paths),
                        })

        return {
            "success": True,
            "scanned_files": scanned_count,
            "duplicate_groups": len(duplicates),
            "duplicates": duplicates,
            "note": "Duplicates detected. Deletion requires explicit approval."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_directory_size(path: str = "~") -> Dict[str, Any]:
    """
    Calculates total size and item counts for a directory.
    """
    try:
        canonical = resolve_safe_path(path)
        if not canonical.is_dir():
            return {"success": False, "error": f"Path is not a directory: '{path}'"}

        total_bytes = 0
        file_count = 0
        dir_count = 0

        for root, dirs, files in os.walk(canonical):
            dir_count += len(dirs)
            for f in files:
                try:
                    total_bytes += (Path(root) / f).stat().st_size
                    file_count += 1
                except Exception:
                    pass

        size_mb = f"{total_bytes / (1024 * 1024):.2f} MB"
        size_gb = f"{total_bytes / (1024**3):.2f} GB"

        return {
            "success": True,
            "path": str(canonical),
            "bytes": total_bytes,
            "size_human": size_gb if total_bytes > 1024**3 else size_mb,
            "file_count": file_count,
            "directory_count": dir_count,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------------------
# 2. Reading Operations
# -------------------------------------------------------------

def read_file(path: str, max_bytes: int = 64 * 1024, offset: int = 0) -> Dict[str, Any]:
    """
    Reads readable content from a text/code file within strict size limits.
    """
    try:
        canonical = resolve_safe_path(path)
        if not canonical.is_file():
            return {"success": False, "error": f"File does not exist: '{path}'"}

        is_sens, sens_reason = is_sensitive_path(canonical)
        if is_sens:
            return {
                "success": False,
                "error": f"Sensitive file access blocked: {sens_reason}. Explicit approval required.",
                "requires_approval": True,
            }

        content, truncated, total_size = read_text_file_safe(canonical, offset_bytes=offset, max_bytes=max_bytes)
        return {
            "success": True,
            "path": str(canonical),
            "size_bytes": total_size,
            "offset": offset,
            "bytes_returned": len(content.encode("utf-8", errors="replace")),
            "truncated": truncated,
            "content": content,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def read_file_range(path: str, start_line: int = 1, end_line: Optional[int] = None) -> Dict[str, Any]:
    """
    Reads a specific line range from a text/source code file.
    """
    try:
        canonical = resolve_safe_path(path)
        if not canonical.is_file():
            return {"success": False, "error": f"File does not exist: '{path}'"}

        is_sens, sens_reason = is_sensitive_path(canonical)
        if is_sens:
            return {"success": False, "error": f"Sensitive file: {sens_reason}", "requires_approval": True}

        res = read_file_line_range(canonical, start_line=start_line, end_line=end_line)
        res["success"] = True
        return res
    except Exception as e:
        return {"success": False, "error": str(e)}


def read_document(path: str, max_pages: int = 20) -> Dict[str, Any]:
    """
    Extracts text from structured document formats (PDF, DOCX, XLSX, CSV).
    """
    try:
        canonical = resolve_safe_path(path)
        if not canonical.is_file():
            return {"success": False, "error": f"File does not exist: '{path}'"}

        suffix = canonical.suffix.lower()
        if suffix == ".pdf":
            return extract_pdf_document(canonical, max_pages=max_pages)
        elif suffix == ".docx":
            return extract_docx_document(canonical)
        elif suffix in (".xlsx", ".xls"):
            return extract_xlsx_document(canonical)
        elif suffix == ".csv":
            return extract_csv_document(canonical)
        else:
            return {"success": False, "error": f"Unsupported document format: '{suffix}'. Use read_file for plain text/code."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def read_image_metadata(path: str) -> Dict[str, Any]:
    """
    Inspects image dimensions, format, and metadata without loading binary bytes.
    """
    try:
        canonical = resolve_safe_path(path)
        if not canonical.is_file():
            return {"success": False, "error": f"File does not exist: '{path}'"}
        return inspect_image_metadata(canonical)
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------------------
# 3. Writing Operations (Category B - Automatic Backup & Undo)
# -------------------------------------------------------------

def create_directory(path: str) -> Dict[str, Any]:
    """
    Creates a new directory (Category A - Auto Permitted).
    """
    try:
        canonical = resolve_safe_path(path)
        canonical.mkdir(parents=True, exist_ok=True)
        return {
            "success": True,
            "path": str(canonical),
            "message": f"Directory '{canonical}' created successfully."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_file(path: str, content: str, overwrite: bool = False, db_conn=None, conversation_id: str = "") -> Dict[str, Any]:
    """
    Creates a new file. If overwriting, creates a backup first.
    """
    try:
        canonical = resolve_safe_path(path)
        is_sens, sens_reason = is_sensitive_path(canonical)
        if is_sens:
            return {"success": False, "error": f"Cannot create file in sensitive path: {sens_reason}", "requires_approval": True}

        backup_path, orig_hash = None, None
        is_overwrite = canonical.exists()
        if is_overwrite:
            if not overwrite:
                return {"success": False, "error": f"File already exists: '{path}'. Pass overwrite=True to replace."}
            backup_path, orig_hash = create_file_backup(canonical)

        canonical.parent.mkdir(parents=True, exist_ok=True)
        with open(canonical, "w", encoding="utf-8") as f:
            f.write(content)

        new_hash = calculate_sha256(canonical)
        if db_conn:
            record_operation(
                conn=db_conn,
                action="create_file",
                target_path=str(canonical),
                conversation_id=conversation_id,
                original_hash=orig_hash,
                new_hash=new_hash,
                backup_path=backup_path,
                diff_summary=f"Created file ({len(content)} chars)" if not is_overwrite else f"Overwrote file ({len(content)} chars)",
            )

        return {
            "success": True,
            "path": str(canonical),
            "overwritten": is_overwrite,
            "backup_path": backup_path,
            "sha256": new_hash,
            "bytes_written": len(content.encode("utf-8")),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def edit_file(
    path: str,
    old_str: str,
    new_str: str,
    db_conn=None,
    conversation_id: str = ""
) -> Dict[str, Any]:
    """
    Edits an existing text file by replacing old_str with new_str.
    Creates a backup first, records a readable diff, and stores the operation for undo.
    """
    try:
        canonical = resolve_safe_path(path)
        if not canonical.is_file():
            return {"success": False, "error": f"File does not exist: '{path}'"}

        is_sens, sens_reason = is_sensitive_path(canonical)
        if is_sens:
            return {"success": False, "error": f"Editing sensitive file requires explicit approval: {sens_reason}", "requires_approval": True}

        with open(canonical, "r", encoding="utf-8", errors="replace") as f:
            original_content = f.read()

        if old_str not in original_content:
            return {
                "success": False,
                "error": f"Target snippet 'old_str' was not found in '{canonical.name}'. Please inspect the file and provide the exact existing text.",
            }

        # 1. Back up original file
        backup_path, orig_hash = create_file_backup(canonical)

        # 2. Generate unified diff
        new_content = original_content.replace(old_str, new_str, 1)
        diff_lines = list(difflib.unified_diff(
            original_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{canonical.name}",
            tofile=f"b/{canonical.name}",
            n=3
        ))
        diff_str = "".join(diff_lines)

        # 3. Write atomically
        temp_path = canonical.with_suffix(f"{canonical.suffix}.tmp.{os.getpid()}")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        temp_path.replace(canonical)

        new_hash = calculate_sha256(canonical)

        # 4. Record operation in SQLite
        op_id = None
        if db_conn:
            op_id = record_operation(
                conn=db_conn,
                action="edit_file",
                target_path=str(canonical),
                conversation_id=conversation_id,
                original_hash=orig_hash,
                new_hash=new_hash,
                backup_path=backup_path,
                diff_summary=diff_str,
            )

        return {
            "success": True,
            "path": str(canonical),
            "operation_id": op_id,
            "backup_path": backup_path,
            "diff": diff_str,
            "sha256": new_hash,
            "message": f"File '{canonical.name}' updated successfully.",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def rename_file(path: str, new_name: str, db_conn=None, conversation_id: str = "") -> Dict[str, Any]:
    """
    Renames a file or directory within its current folder.
    """
    try:
        canonical = resolve_safe_path(path)
        if not canonical.exists():
            return {"success": False, "error": f"Item does not exist: '{path}'"}

        # Validate new_name is a simple filename without path separators
        clean_new_name = Path(new_name).name
        dest = canonical.parent / clean_new_name
        dest_canonical = resolve_safe_path(str(dest))

        if dest_canonical.exists():
            return {"success": False, "error": f"Destination already exists: '{dest_canonical.name}'"}

        backup_path, orig_hash = None, None
        if canonical.is_file():
            backup_path, orig_hash = create_file_backup(canonical)

        canonical.rename(dest_canonical)

        op_id = None
        if db_conn:
            op_id = record_operation(
                conn=db_conn,
                action="rename_file",
                target_path=str(canonical),
                dest_path=str(dest_canonical),
                conversation_id=conversation_id,
                original_hash=orig_hash,
                new_hash=calculate_sha256(dest_canonical) if dest_canonical.is_file() else None,
                backup_path=backup_path,
                diff_summary=f"Renamed '{canonical.name}' to '{dest_canonical.name}'",
            )

        return {
            "success": True,
            "old_path": str(canonical),
            "new_path": str(dest_canonical),
            "operation_id": op_id,
            "message": f"Renamed to '{dest_canonical.name}'."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def move_file(source_path: str, destination_path: str, db_conn=None, conversation_id: str = "") -> Dict[str, Any]:
    """
    Moves a file or directory to a new safe path.
    """
    try:
        src = resolve_safe_path(source_path)
        dest = resolve_safe_path(destination_path)

        if not src.exists():
            return {"success": False, "error": f"Source does not exist: '{source_path}'"}

        if dest.is_dir():
            target_dest = dest / src.name
        else:
            target_dest = dest

        if target_dest.exists():
            return {"success": False, "error": f"Target already exists: '{target_dest}'"}

        backup_path, orig_hash = None, None
        if src.is_file():
            backup_path, orig_hash = create_file_backup(src)

        target_dest.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.move(str(src), str(target_dest))

        op_id = None
        if db_conn:
            op_id = record_operation(
                conn=db_conn,
                action="move_file",
                target_path=str(src),
                dest_path=str(target_dest),
                conversation_id=conversation_id,
                original_hash=orig_hash,
                new_hash=calculate_sha256(target_dest) if target_dest.is_file() else None,
                backup_path=backup_path,
                diff_summary=f"Moved from '{src}' to '{target_dest}'",
            )

        return {
            "success": True,
            "source": str(src),
            "destination": str(target_dest),
            "operation_id": op_id,
            "message": f"Moved successfully to '{target_dest}'."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def copy_file(source_path: str, destination_path: str, db_conn=None, conversation_id: str = "") -> Dict[str, Any]:
    """
    Copies a file to a new safe path.
    """
    try:
        src = resolve_safe_path(source_path)
        dest = resolve_safe_path(destination_path)

        if not src.is_file():
            return {"success": False, "error": f"Source is not a valid file: '{source_path}'"}

        if dest.is_dir():
            target_dest = dest / src.name
        else:
            target_dest = dest

        target_dest.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(src, target_dest)

        new_hash = calculate_sha256(target_dest)
        op_id = None
        if db_conn:
            op_id = record_operation(
                conn=db_conn,
                action="copy_file",
                target_path=str(src),
                dest_path=str(target_dest),
                conversation_id=conversation_id,
                new_hash=new_hash,
                diff_summary=f"Copied '{src.name}' to '{target_dest}'",
            )

        return {
            "success": True,
            "source": str(src),
            "destination": str(target_dest),
            "operation_id": op_id,
            "sha256": new_hash,
            "message": f"Copied to '{target_dest}'."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------------------
# 4. Deletion Operation (Category C - Requires Explicit Approval)
# -------------------------------------------------------------

def delete_file(
    path: str,
    approval_granted: bool = False,
    db_conn=None,
    conversation_id: str = ""
) -> Dict[str, Any]:
    """
    Permanently deletes a file or directory.
    ALWAYS requires explicit user approval.
    """
    try:
        canonical = resolve_safe_path(path)
        if not canonical.exists():
            return {"success": False, "error": f"Item does not exist: '{path}'"}

        if not approval_granted:
            return {
                "success": False,
                "error": f"Deletion of '{canonical}' requires explicit user approval.",
                "requires_approval": True,
                "action": "delete_file",
                "target_path": str(canonical),
                "risk_level": "high",
            }

        backup_path, orig_hash = None, None
        if canonical.is_file():
            # Create a backup before deleting so it can still be undone if needed
            backup_path, orig_hash = create_file_backup(canonical)
            canonical.unlink()
        elif canonical.is_dir():
            import shutil
            shutil.rmtree(canonical)

        op_id = None
        if db_conn:
            op_id = record_operation(
                conn=db_conn,
                action="delete_file",
                target_path=str(canonical),
                conversation_id=conversation_id,
                original_hash=orig_hash,
                backup_path=backup_path,
                approval_status="approved",
                diff_summary=f"Deleted '{canonical}'",
            )

        return {
            "success": True,
            "path": str(canonical),
            "operation_id": op_id,
            "backup_path": backup_path,
            "message": f"Successfully deleted '{canonical}'."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------------------
# 5. Terminal Execution (Bubblewrap Sandbox)
# -------------------------------------------------------------

async def run_terminal_command(
    command: str,
    args: Optional[List[str]] = None,
    cwd: Optional[str] = None,
    approval_granted: bool = False
) -> Dict[str, Any]:
    """
    Runs a terminal command within the restricted Bubblewrap sandbox.
    Permits allowlisted safe inspection commands automatically.
    Non-allowlisted commands require explicit approval.
    """
    is_safe, risk_level, reason = is_terminal_command_allowlisted(command, args)

    if not is_safe and not approval_granted:
        return {
            "success": False,
            "error": f"Terminal command '{command}' requires user approval: {reason}",
            "requires_approval": True,
            "command": command,
            "args": args or [],
            "cwd": cwd or str(get_home_directory()),
            "risk_level": risk_level,
            "reason": reason,
        }

    work_dir = resolve_safe_path(cwd) if cwd else get_home_directory()
    sandbox = BwrapSandbox(allowed_work_dir=work_dir)

    # Allowlisted commands run read-only; approved commands get read-write in cwd
    read_only = is_safe
    result = await sandbox.execute_command(
        command=command,
        args=args or [],
        cwd=work_dir,
        read_only=read_only
    )
    return result
