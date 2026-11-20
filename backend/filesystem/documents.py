"""
Moso AI — Document & Media Reader
Safe text extraction, range reading, and metadata inspection for supported formats:
- Plain text & code files (TXT, MD, JSON, YAML, TOML, PY, TS, JS, CPP, JAVA, HTML, CSS, etc.)
- Office documents: PDF (pypdf), DOCX (XML stream extraction), XLSX (XML sheet extraction), CSV
- Media files: image dimensions, format, file size without loading binary bytes into context.
"""

import os
import csv
import struct
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


def read_text_file_safe(
    file_path: Path,
    offset_bytes: int = 0,
    max_bytes: int = 64 * 1024,
    encoding: str = "utf-8"
) -> Tuple[str, bool, int]:
    """
    Reads up to max_bytes from a text file starting at offset_bytes.
    Returns (content_text: str, is_truncated: bool, total_file_size: int).
    """
    total_size = file_path.stat().st_size
    with open(file_path, "r", encoding=encoding, errors="replace") as f:
        if offset_bytes > 0:
            f.seek(offset_bytes)
        chunk = f.read(max_bytes)
        is_truncated = (offset_bytes + len(chunk.encode(encoding, errors="replace"))) < total_size
        return chunk, is_truncated, total_size


def read_file_line_range(
    file_path: Path,
    start_line: int = 1,
    end_line: Optional[int] = None,
    max_lines: int = 500
) -> Dict[str, Any]:
    """
    Reads lines [start_line, end_line] (1-indexed inclusive) from a source code or text file.
    Prevents reading excessively large regions into model context.
    """
    lines: List[str] = []
    total_lines = 0
    actual_start = max(1, start_line)
    actual_end = end_line if end_line is not None else (actual_start + max_lines - 1)
    if actual_end < actual_start:
        actual_end = actual_start + max_lines - 1

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for idx, line in enumerate(f, start=1):
            total_lines += 1
            if actual_start <= idx <= actual_end and len(lines) < max_lines:
                lines.append(f"{idx}: {line.rstrip('\\r\\n')}")

    return {
        "file": str(file_path),
        "start_line": actual_start,
        "end_line": min(actual_end, total_lines),
        "total_lines": total_lines,
        "lines_returned": len(lines),
        "content": "\n".join(lines),
        "truncated": (len(lines) == max_lines and actual_end < total_lines),
    }


def extract_pdf_document(file_path: Path, max_pages: int = 25) -> Dict[str, Any]:
    """
    Extracts text and page structure from a PDF file using pypdf.
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        num_pages = len(reader.pages)
        pages_to_read = min(num_pages, max_pages)

        extracted_pages = []
        total_chars = 0
        for i in range(pages_to_read):
            text = reader.pages[i].extract_text() or ""
            total_chars += len(text)
            extracted_pages.append({
                "page": i + 1,
                "char_count": len(text),
                "text": text[:4000]  # Cap per page
            })

        return {
            "success": True,
            "format": "pdf",
            "total_pages": num_pages,
            "pages_read": pages_to_read,
            "char_count": total_chars,
            "pages": extracted_pages,
        }
    except Exception as e:
        return {"success": False, "format": "pdf", "error": f"PDF extraction failed: {str(e)}"}


def extract_docx_document(file_path: Path, max_paragraphs: int = 200) -> Dict[str, Any]:
    """
    Extracts structured text from a DOCX file using python's built-in zipfile and XML parser.
    Zero external dependencies.
    """
    try:
        with zipfile.ZipFile(file_path, "r") as docx:
            xml_content = docx.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            # WML namespace
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            paragraphs = []
            for p in tree.iterfind(".//w:p", ns):
                texts = [node.text for node in p.iterfind(".//w:t", ns) if node.text]
                if texts:
                    full_p = "".join(texts).strip()
                    if full_p:
                        paragraphs.append(full_p)
                if len(paragraphs) >= max_paragraphs:
                    break

            combined_text = "\n\n".join(paragraphs)
            return {
                "success": True,
                "format": "docx",
                "paragraph_count": len(paragraphs),
                "text": combined_text[:20000],
                "truncated": len(paragraphs) == max_paragraphs,
            }
    except Exception as e:
        return {"success": False, "format": "docx", "error": f"DOCX extraction failed: {str(e)}"}


def extract_xlsx_document(file_path: Path, max_rows: int = 100) -> Dict[str, Any]:
    """
    Extracts preview sheet rows from an XLSX workbook using built-in zipfile and XML parser.
    Zero external dependencies.
    """
    try:
        with zipfile.ZipFile(file_path, "r") as xlsx:
            # 1. Read shared strings
            shared_strings: List[str] = []
            if "xl/sharedStrings.xml" in xlsx.namelist():
                ss_content = xlsx.read("xl/sharedStrings.xml")
                ss_tree = ET.fromstring(ss_content)
                ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for si in ss_tree.iterfind(".//s:si", ns):
                    texts = [t.text for t in si.iterfind(".//s:t", ns) if t.text]
                    shared_strings.append("".join(texts))

            # 2. Read first sheet
            sheet_rows = []
            if "xl/worksheets/sheet1.xml" in xlsx.namelist():
                sheet_content = xlsx.read("xl/worksheets/sheet1.xml")
                s_tree = ET.fromstring(sheet_content)
                ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for row_node in s_tree.iterfind(".//s:row", ns):
                    row_vals = []
                    for c_node in row_node.iterfind("./s:c", ns):
                        t_type = c_node.get("t")
                        v_node = c_node.find("./s:v", ns)
                        val = v_node.text if (v_node is not None and v_node.text) else ""
                        if t_type == "s" and val.isdigit():
                            idx = int(val)
                            val = shared_strings[idx] if idx < len(shared_strings) else val
                        row_vals.append(val)
                    if any(row_vals):
                        sheet_rows.append(row_vals)
                    if len(sheet_rows) >= max_rows:
                        break

            return {
                "success": True,
                "format": "xlsx",
                "rows_extracted": len(sheet_rows),
                "rows": sheet_rows,
            }
    except Exception as e:
        return {"success": False, "format": "xlsx", "error": f"XLSX extraction failed: {str(e)}"}


def extract_csv_document(file_path: Path, max_rows: int = 100) -> Dict[str, Any]:
    """
    Reads rows from a CSV file.
    """
    try:
        rows = []
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for idx, r in enumerate(reader):
                rows.append(r)
                if len(rows) >= max_rows:
                    break
        return {
            "success": True,
            "format": "csv",
            "rows_extracted": len(rows),
            "rows": rows,
        }
    except Exception as e:
        return {"success": False, "format": "csv", "error": f"CSV reading failed: {str(e)}"}


def inspect_image_metadata(file_path: Path) -> Dict[str, Any]:
    """
    Extracts image format, dimensions (width, height), and file size using standard library struct.
    Never loads huge binary payload into LLM context.
    Supports PNG, JPEG, GIF, BMP, WebP.
    """
    stat = file_path.stat()
    size_bytes = stat.st_size
    size_mb = f"{size_bytes / (1024 * 1024):.2f} MB" if size_bytes >= 1024 * 1024 else f"{size_bytes / 1024:.1f} KB"

    width, height, img_format = None, None, "Unknown"

    try:
        with open(file_path, "rb") as f:
            header = f.read(64)

            # PNG: bytes 12-24 contain IHDR width & height
            if header.startswith(b"\x89PNG\r\n\x1a\n"):
                img_format = "PNG"
                f.seek(16)
                w, h = struct.unpack(">LL", f.read(8))
                width, height = int(w), int(h)

            # GIF: bytes 6-10 contain width & height
            elif header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
                img_format = "GIF"
                w, h = struct.unpack("<HH", header[6:10])
                width, height = int(w), int(h)

            # BMP: bytes 18-26 contain width & height
            elif header.startswith(b"BM"):
                img_format = "BMP"
                f.seek(18)
                w, h = struct.unpack("<LL", f.read(8))
                width, height = int(w), int(h)

            # WebP: RIFF....WEBP
            elif header.startswith(b"RIFF") and header[8:12] == b"WEBP":
                img_format = "WebP"
                # VP8 / VP8L chunk
                f.seek(12)
                chunk_type = f.read(4)
                if chunk_type == b"VP8 ":
                    f.seek(26)
                    w, h = struct.unpack("<HH", f.read(4))
                    width, height = int(w & 0x3FFF), int(h & 0x3FFF)
                elif chunk_type == b"VP8L":
                    f.seek(21)
                    b0, b1, b2, b3 = struct.unpack("BBBB", f.read(4))
                    width = 1 + (((b1 & 0x3F) << 8) | b0)
                    height = 1 + (((b3 & 0xF) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))

            # JPEG: Search for SOF0/SOF2 marker
            elif header.startswith(b"\xff\xd8"):
                img_format = "JPEG"
                f.seek(2)
                b = f.read(1)
                while b:
                    if b == b"\xff":
                        marker = f.read(1)
                        if marker in [b"\xc0", b"\xc1", b"\xc2", b"\xc3"]:
                            f.seek(3, 1)  # Skip length and precision
                            h, w = struct.unpack(">HH", f.read(4))
                            width, height = int(w), int(h)
                            break
                        elif marker == b"\xda" or marker == b"":  # Start of spectral data
                            break
                        else:
                            length_bytes = f.read(2)
                            if len(length_bytes) == 2:
                                length = struct.unpack(">H", length_bytes)[0]
                                f.seek(length - 2, 1)
                            else:
                                break
                    b = f.read(1)
    except Exception:
        pass

    return {
        "success": True,
        "filename": file_path.name,
        "path": str(file_path),
        "format": img_format,
        "dimensions": f"{width}x{height}" if width and height else "Unknown",
        "width": width,
        "height": height,
        "file_size": size_mb,
        "bytes": size_bytes,
        "modified_at": stat.st_mtime,
    }
