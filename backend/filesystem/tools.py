"""
Moso AI — Filesystem Tools Definition and Dispatcher for Ollama
Defines the JSON function calling schema for all filesystem operations,
executes tool requests, tracks backups, and handles approval requests.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from .operations import (
    list_directory,
    get_file_info,
    search_files,
    search_file_contents,
    find_duplicate_files,
    get_directory_size,
    read_file,
    read_file_range,
    read_document,
    read_image_metadata,
    create_file,
    create_directory,
    edit_file,
    rename_file,
    move_file,
    copy_file,
    delete_file,
    run_terminal_command,
)
from .history import undo_fs_operation, get_recent_operations
from .security import get_home_directory, resolve_safe_path, classify_operation_autonomy


FILESYSTEM_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and folders in a local directory in the user's home directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (defaults to '~')."},
                    "recursive": {"type": "boolean", "description": "Whether to list subdirectories recursively."},
                    "max_depth": {"type": "integer", "description": "Maximum recursion depth (default 2)."},
                    "include_hidden": {"type": "boolean", "description": "Whether to include hidden files (dotfiles)."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_info",
            "description": "Get detailed metadata (size, timestamps, MIME, permissions) for a file or directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file or directory."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for files by filename or glob pattern across the user's home directory (e.g. '*.pdf', 'notes*').",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Filename pattern or glob query."},
                    "path": {"type": "string", "description": "Base directory to start searching (defaults to '~')."},
                    "max_results": {"type": "integer", "description": "Maximum number of matching files to return (default 50)."}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_file_contents",
            "description": "Search file text contents (grep-like) across files in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text substring to search for."},
                    "path": {"type": "string", "description": "Base directory to search in (defaults to '~')."},
                    "file_extensions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of file extensions to limit to (e.g. ['.py', '.ts'])."
                    },
                    "max_results": {"type": "integer", "description": "Maximum number of occurrences to return (default 30)."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_duplicate_files",
            "description": "Scan a directory for duplicate files based on size and SHA-256 hash without deleting anything.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory_path": {"type": "string", "description": "Directory to scan (defaults to '~')."},
                    "min_size_bytes": {"type": "integer", "description": "Minimum file size to consider in bytes (default 1024)."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_directory_size",
            "description": "Calculate total size, file count, and folder count for a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read content from a text or source code file with byte limits to prevent context overflow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file."},
                    "max_bytes": {"type": "integer", "description": "Max bytes to read (default 65536)."},
                    "offset": {"type": "integer", "description": "Byte offset to start reading from."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file_range",
            "description": "Read specific lines from a source code or text file (e.g. lines 10 to 50).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file."},
                    "start_line": {"type": "integer", "description": "1-based starting line number."},
                    "end_line": {"type": "integer", "description": "1-based ending line number."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "Extract text and structure from complex documents (PDF, DOCX, XLSX, CSV).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the document."},
                    "max_pages": {"type": "integer", "description": "Maximum pages/paragraphs to extract (default 20)."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_image_metadata",
            "description": "Inspect image dimensions, format, and file size without reading binary data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the image."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new file or overwrite an existing file (an automatic backup is preserved if overwriting).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Target file path."},
                    "content": {"type": "string", "description": "Text content to write."},
                    "overwrite": {"type": "boolean", "description": "Whether to overwrite if file already exists."}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a new folder in the user's home directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Folder path to create."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace a specific text snippet in an existing file. Automatically creates a backup and tracks diff for undo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file."},
                    "old_str": {"type": "string", "description": "Exact text snippet to be replaced."},
                    "new_str": {"type": "string", "description": "Replacement text."}
                },
                "required": ["path", "old_str", "new_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rename_file",
            "description": "Rename a file or folder in its current location (backup preserved).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Current file path."},
                    "new_name": {"type": "string", "description": "New filename (just the name, not a full path)."}
                },
                "required": ["path", "new_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "Move a file or folder to a new destination in the home directory (backup preserved).",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_path": {"type": "string", "description": "Source path."},
                    "destination_path": {"type": "string", "description": "Destination path or directory."}
                },
                "required": ["source_path", "destination_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "Copy a file to a new destination path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_path": {"type": "string", "description": "Source path."},
                    "destination_path": {"type": "string", "description": "Destination path."}
                },
                "required": ["source_path", "destination_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file or folder. (Requires explicit user approval before executing).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to delete."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_terminal_command",
            "description": "Run a validated command in a restricted Linux Bubblewrap sandbox. Allowlisted safe commands (pwd, ls, find, git status, git diff, du, df) run automatically; others require approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command executable (e.g. 'git', 'ls', 'pytest')."},
                    "args": {"type": "array", "items": {"type": "string"}, "description": "Command arguments."},
                    "cwd": {"type": "string", "description": "Working directory path."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "undo_operation",
            "description": "Revert a previous file edit, rename, move, or creation operation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation_id": {"type": "string", "description": "The ID of the operation to undo."}
                },
                "required": ["operation_id"]
            }
        }
    }
]


async def execute_filesystem_tool(
    name: str,
    args: Dict[str, Any],
    db_conn=None,
    conversation_id: str = "",
    assistant_msg_id: str = "",
    approval_granted: bool = False
) -> Tuple[str, Dict[str, Any], bool, Optional[Dict[str, Any]]]:
    """
    Executes a filesystem tool call with strict boundary validation.
    Returns:
        (result_text: str, metadata: Dict, requires_approval: bool, approval_request: Optional[Dict])
    """
    try:
        # Discovery tools
        if name == "list_directory":
            res = list_directory(
                path=args.get("path", "~"),
                recursive=args.get("recursive", False),
                max_depth=args.get("max_depth", 2),
                include_hidden=args.get("include_hidden", False)
            )
            return json.dumps(res, indent=2), res, False, None

        elif name == "get_file_info":
            res = get_file_info(args.get("path", ""))
            return json.dumps(res, indent=2), res, False, None

        elif name == "search_files":
            res = search_files(
                pattern=args.get("pattern", ""),
                path=args.get("path", "~"),
                max_results=args.get("max_results", 50),
            )
            return json.dumps(res, indent=2), res, False, None

        elif name == "search_file_contents":
            res = search_file_contents(
                query=args.get("query", ""),
                path=args.get("path", "~"),
                file_extensions=args.get("file_extensions"),
                max_results=args.get("max_results", 30),
            )
            return json.dumps(res, indent=2), res, False, None

        elif name == "find_duplicate_files":
            res = find_duplicate_files(
                directory_path=args.get("directory_path", "~"),
                min_size_bytes=args.get("min_size_bytes", 1024),
            )
            return json.dumps(res, indent=2), res, False, None

        elif name == "get_directory_size":
            res = get_directory_size(args.get("path", "~"))
            return json.dumps(res, indent=2), res, False, None

        # Reading tools
        elif name == "read_file":
            res = read_file(
                path=args.get("path", ""),
                max_bytes=args.get("max_bytes", 64 * 1024),
                offset=args.get("offset", 0),
            )
            if res.get("requires_approval") and not approval_granted:
                approval_payload = {
                    "action": "read_sensitive_file",
                    "target_path": args.get("path", ""),
                    "risk_level": "critical",
                    "explanation": res.get("error"),
                }
                return f"[APPROVAL REQUIRED] {res.get('error')}", res, True, approval_payload
            return res.get("content", json.dumps(res, indent=2)), res, False, None

        elif name == "read_file_range":
            res = read_file_range(
                path=args.get("path", ""),
                start_line=args.get("start_line", 1),
                end_line=args.get("end_line"),
            )
            if res.get("requires_approval") and not approval_granted:
                approval_payload = {
                    "action": "read_sensitive_file",
                    "target_path": args.get("path", ""),
                    "risk_level": "critical",
                    "explanation": res.get("error"),
                }
                return f"[APPROVAL REQUIRED] {res.get('error')}", res, True, approval_payload
            return res.get("content", json.dumps(res, indent=2)), res, False, None

        elif name == "read_document":
            res = read_document(
                path=args.get("path", ""),
                max_pages=args.get("max_pages", 20),
            )
            return json.dumps(res, indent=2), res, False, None

        elif name == "read_image_metadata":
            res = read_image_metadata(args.get("path", ""))
            return json.dumps(res, indent=2), res, False, None

        # Writing tools
        elif name == "create_directory":
            res = create_directory(args.get("path", ""))
            return json.dumps(res, indent=2), res, False, None

        elif name == "create_file":
            res = create_file(
                path=args.get("path", ""),
                content=args.get("content", ""),
                overwrite=args.get("overwrite", False),
                db_conn=db_conn,
                conversation_id=conversation_id,
            )
            if res.get("requires_approval") and not approval_granted:
                approval_payload = {
                    "action": "create_sensitive_file",
                    "target_path": args.get("path", ""),
                    "risk_level": "critical",
                    "explanation": res.get("error"),
                }
                return f"[APPROVAL REQUIRED] {res.get('error')}", res, True, approval_payload
            return json.dumps(res, indent=2), res, False, None

        elif name == "edit_file":
            res = edit_file(
                path=args.get("path", ""),
                old_str=args.get("old_str", ""),
                new_str=args.get("new_str", ""),
                db_conn=db_conn,
                conversation_id=conversation_id,
            )
            if res.get("requires_approval") and not approval_granted:
                approval_payload = {
                    "action": "edit_sensitive_file",
                    "target_path": args.get("path", ""),
                    "risk_level": "critical",
                    "explanation": res.get("error"),
                }
                return f"[APPROVAL REQUIRED] {res.get('error')}", res, True, approval_payload
            return json.dumps(res, indent=2), res, False, None

        elif name == "rename_file":
            res = rename_file(
                path=args.get("path", ""),
                new_name=args.get("new_name", ""),
                db_conn=db_conn,
                conversation_id=conversation_id,
            )
            return json.dumps(res, indent=2), res, False, None

        elif name == "move_file":
            res = move_file(
                source_path=args.get("source_path", ""),
                destination_path=args.get("destination_path", ""),
                db_conn=db_conn,
                conversation_id=conversation_id,
            )
            return json.dumps(res, indent=2), res, False, None

        elif name == "copy_file":
            res = copy_file(
                source_path=args.get("source_path", ""),
                destination_path=args.get("destination_path", ""),
                db_conn=db_conn,
                conversation_id=conversation_id,
            )
            return json.dumps(res, indent=2), res, False, None

        elif name == "delete_file":
            res = delete_file(
                path=args.get("path", ""),
                approval_granted=approval_granted,
                db_conn=db_conn,
                conversation_id=conversation_id,
            )
            if res.get("requires_approval") and not approval_granted:
                approval_payload = {
                    "action": "delete_file",
                    "target_path": res.get("target_path", args.get("path", "")),
                    "risk_level": "high",
                    "explanation": res.get("error"),
                }
                return f"[APPROVAL REQUIRED] {res.get('error')}", res, True, approval_payload
            return json.dumps(res, indent=2), res, False, None

        elif name == "run_terminal_command":
            res = await run_terminal_command(
                command=args.get("command", ""),
                args=args.get("args"),
                cwd=args.get("cwd"),
                approval_granted=approval_granted,
            )
            if res.get("requires_approval") and not approval_granted:
                approval_payload = {
                    "action": "run_terminal_command",
                    "command": res.get("command"),
                    "args": res.get("args"),
                    "cwd": res.get("cwd"),
                    "risk_level": res.get("risk_level", "high"),
                    "explanation": res.get("reason"),
                }
                return f"[APPROVAL REQUIRED] {res.get('error')}", res, True, approval_payload
            out = res.get("stdout") or res.get("stderr") or f"Exited with code {res.get('exit_code')}"
            return out, res, False, None

        elif name == "undo_operation":
            if not db_conn:
                return json.dumps({"success": False, "error": "Database connection required for undo."}), {}, False, None
            res = undo_fs_operation(db_conn, args.get("operation_id", ""))
            return json.dumps(res, indent=2), res, False, None

        else:
            return json.dumps({"success": False, "error": f"Unknown filesystem tool: '{name}'"}), {}, False, None

    except Exception as e:
        err_dict = {"success": False, "error": f"Tool execution failed: {str(e)}"}
        return json.dumps(err_dict), err_dict, False, None
