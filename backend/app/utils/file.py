"""File handling utilities."""

import os
import uuid
from datetime import datetime
from typing import Tuple

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "application/octet-stream",  # fallback
}


def generate_server_filename(original_filename: str) -> str:
    """Generate a unique server-side filename using UUID."""
    ext = get_file_extension(original_filename)
    return f"{uuid.uuid4().hex}{ext}"


def get_file_extension(filename: str) -> str:
    """Extract file extension from filename."""
    _, ext = os.path.splitext(filename)
    return ext.lower()


def is_allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    ext = get_file_extension(filename)
    return ext in ALLOWED_EXTENSIONS


def get_upload_path(base_dir: str, filename: str) -> Tuple[str, str]:
    """Generate the upload path with date-based directory structure.
    
    Returns:
        Tuple of (relative_path, full_path)
    """
    now = datetime.now()
    date_dir = os.path.join(
        base_dir,
        str(now.year),
        f"{now.month:02d}",
        f"{now.day:02d}",
    )

    # Create directory if not exists
    os.makedirs(date_dir, exist_ok=True)

    server_filename = generate_server_filename(filename)
    relative_path = os.path.join(
        str(now.year),
        f"{now.month:02d}",
        f"{now.day:02d}",
        server_filename,
    )
    full_path = os.path.join(date_dir, server_filename)

    return relative_path, full_path


def get_file_type(filename: str) -> str:
    """Get file type from extension."""
    ext = get_file_extension(filename)
    type_map = {
        ".pdf": "pdf",
        ".docx": "docx",
        ".txt": "txt",
        ".md": "md",
    }
    return type_map.get(ext, "unknown")
