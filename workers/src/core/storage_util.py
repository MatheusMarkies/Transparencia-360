import os
from pathlib import Path

def get_download_dir(subfolder: str) -> Path:
    """
    Returns the centralized download directory for the given subfolder.
    Creates it if it doesn't exist.
    """
    # Assuming this file is at workers/src/core/storage_util.py
    # So parent.parent.parent is the workers/ dir, and another parent is the root dir.
    # Root -> data -> downloads -> subfolder
    base_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "downloads" / subfolder
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir

def save_downloaded_file(subfolder: str, filename: str, content: str) -> Path:
    """
    Saves a text content to a specific file in the central download directory.
    """
    target_dir = get_download_dir(subfolder)
    file_path = target_dir / filename
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path
