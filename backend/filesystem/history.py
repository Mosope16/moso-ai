"""
Moso AI — Filesystem Operation History, Backups & Undo Engine
Maintains recoverable backup versions, atomic file modifications, and persistent SQLite history.
"""

import os
import shutil
import hashlib
import sqlite3
import datetime
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from .security import get_home_directory, resolve_safe_path

# Default backup storage directory on Arch Linux
DEFAULT_BACKUP_DIR = get_home_directory() / ".local" / "share" / "moso-ai" / "backups"


def ensure_backup_dir() -> Path:
    """Creates the backup directory with secure 0700 permissions."""
    b_dir = Path(os.getenv("MOSO_BACKUP_DIR", str(DEFAULT_BACKUP_DIR))).resolve()
    b_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(b_dir, 0o700)
    except Exception:
        pass
    return b_dir


def calculate_sha256(path: Path) -> Optional[str]:
    """Calculates SHA256 checksum of a file."""
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(64 * 1024):
            h.update(chunk)
    return h.hexdigest()


def create_file_backup(source_path: Path) -> Tuple[Optional[str], Optional[str]]:
    """
    Creates an atomic recoverable copy of a file before modification.
    Returns (backup_file_path: Optional[str], file_sha256: Optional[str]).
    """
    if not source_path.is_file():
        return None, None

    b_dir = ensure_backup_dir()
    file_hash = calculate_sha256(source_path) or "empty"
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    rand_suffix = uuid.uuid4().hex[:8]
    backup_filename = f"{source_path.name}.{timestamp}.{rand_suffix}.bak"
    backup_dest = b_dir / backup_filename

    shutil.copy2(source_path, backup_dest)
    try:
        os.chmod(backup_dest, 0o600)
    except Exception:
        pass

    return str(backup_dest), file_hash


def init_filesystem_tables(conn: sqlite3.Connection):
    """Initializes SQLite tables for operation history and pending approvals."""
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS fs_operations (
            id TEXT PRIMARY KEY,
            conversation_id TEXT,
            action TEXT NOT NULL,
            target_path TEXT NOT NULL,
            dest_path TEXT,
            original_hash TEXT,
            new_hash TEXT,
            backup_path TEXT,
            diff_summary TEXT,
            model_used TEXT,
            autonomy_category TEXT,
            requires_approval INTEGER DEFAULT 0,
            approval_status TEXT DEFAULT 'auto_permitted',
            status TEXT DEFAULT 'completed',
            created_at TEXT NOT NULL,
            undone_at TEXT
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_fs_ops_conv ON fs_operations(conversation_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_fs_ops_time ON fs_operations(created_at DESC)")

    c.execute("""
        CREATE TABLE IF NOT EXISTS fs_pending_approvals (
            id TEXT PRIMARY KEY,
            conversation_id TEXT,
            action TEXT NOT NULL,
            target_path TEXT NOT NULL,
            params_json TEXT,
            risk_level TEXT NOT NULL,
            explanation TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            resolved_at TEXT
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_fs_appr_status ON fs_pending_approvals(status)")
    conn.commit()


def record_operation(
    conn: sqlite3.Connection,
    action: str,
    target_path: str,
    conversation_id: str = "",
    dest_path: Optional[str] = None,
    original_hash: Optional[str] = None,
    new_hash: Optional[str] = None,
    backup_path: Optional[str] = None,
    diff_summary: Optional[str] = None,
    model_used: str = "qwen3.5:4b",
    autonomy_category: str = "B",
    requires_approval: bool = False,
    approval_status: str = "auto_permitted",
    status: str = "completed"
) -> str:
    """Inserts a filesystem modification into the persistent history table."""
    op_id = f"fs_op_{uuid.uuid4()}"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    c = conn.cursor()
    c.execute("""
        INSERT INTO fs_operations (
            id, conversation_id, action, target_path, dest_path,
            original_hash, new_hash, backup_path, diff_summary,
            model_used, autonomy_category, requires_approval,
            approval_status, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        op_id, conversation_id, action, target_path, dest_path,
        original_hash, new_hash, backup_path, diff_summary,
        model_used, autonomy_category, 1 if requires_approval else 0,
        approval_status, status, now
    ))
    conn.commit()
    return op_id


def get_recent_operations(conn: sqlite3.Connection, limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieves the recent filesystem operation records."""
    c = conn.cursor()
    c.execute("""
        SELECT id, conversation_id, action, target_path, dest_path,
               backup_path, diff_summary, model_used, status, created_at, undone_at
        FROM fs_operations
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    return [dict(r) for r in c.fetchall()]


def undo_fs_operation(conn: sqlite3.Connection, operation_id: str) -> Dict[str, Any]:
    """
    Safely reverts a previous filesystem modification using the recorded backup or inverse action.
    """
    c = conn.cursor()
    c.execute("SELECT * FROM fs_operations WHERE id = ?", (operation_id,))
    row = c.fetchone()
    if not row:
        return {"success": False, "error": f"Operation '{operation_id}' not found."}

    op = dict(row)
    if op.get("status") == "undone":
        return {"success": False, "error": f"Operation '{operation_id}' has already been undone."}

    action = op["action"]
    target_path = Path(op["target_path"])
    dest_path = Path(op["dest_path"]) if op.get("dest_path") else None
    backup_path = Path(op["backup_path"]) if op.get("backup_path") else None
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    try:
        # Revert Edit: restore from backup
        if action in ("edit_file", "apply_file_patch"):
            if not backup_path or not backup_path.is_file():
                return {"success": False, "error": "Cannot undo: backup file is missing or corrupted."}
            shutil.copy2(backup_path, target_path)

        # Revert Create File: remove the newly created file if still present
        elif action == "create_file":
            if target_path.is_file():
                # Back up before deleting
                create_file_backup(target_path)
                target_path.unlink()

        # Revert Move / Rename: move back from destination to target
        elif action in ("move_file", "rename_file"):
            if not dest_path or not dest_path.exists():
                return {"success": False, "error": f"Cannot undo: target '{dest_path}' does not exist."}
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dest_path), str(target_path))

        # Revert Copy: remove the created copy
        elif action == "copy_file":
            if dest_path and dest_path.is_file():
                dest_path.unlink()

        else:
            return {"success": False, "error": f"Action '{action}' is not reversible via automated undo."}

        # Update database record
        c.execute("UPDATE fs_operations SET status = 'undone', undone_at = ? WHERE id = ?", (now, operation_id))
        conn.commit()

        return {
            "success": True,
            "operation_id": operation_id,
            "action": action,
            "message": f"Successfully reverted '{action}' on '{target_path}'.",
            "restored_path": str(target_path),
        }

    except Exception as e:
        return {"success": False, "error": f"Undo failed with exception: {str(e)}"}
