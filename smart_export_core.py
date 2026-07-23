"""Fusion-independent filename rules for Smart Export."""

from datetime import datetime
from pathlib import Path
import re


INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_stem(name):
    """Return a filesystem-safe design name without a trailing extension."""
    stem = Path(name or "Untitled").stem
    stem = INVALID_FILENAME_CHARS.sub("_", stem).strip(" .")
    return stem or "Untitled"


def next_sequence(folder, stem, extension, width=1):
    """Find the first version above all matching ``stem_vN.ext`` files."""
    folder = Path(folder)
    ext = extension.lower().lstrip(".")
    pattern = re.compile(
        rf"^{re.escape(stem)}_v(\d+)\.{re.escape(ext)}$", re.IGNORECASE
    )
    highest = 0
    if folder.is_dir():
        for entry in folder.iterdir():
            match = pattern.match(entry.name)
            if entry.is_file() and match:
                highest = max(highest, int(match.group(1)))
    number = highest + 1
    return f"{stem}_v{number:0{max(width, len(str(number)))}d}.{ext}"


def timestamp_filename(stem, extension, epoch_seconds):
    """Build a local-time filename from a Fusion DataFile creation epoch."""
    if epoch_seconds is None:
        raise ValueError("A saved Fusion history timestamp is required.")
    stamp = datetime.fromtimestamp(float(epoch_seconds)).strftime("%Y-%m-%d_%H-%M-%S")
    return f"{stem}_{stamp}.{extension.lower().lstrip('.')}"


def unique_path(path):
    """Avoid overwriting when multiple history versions share one-second precision."""
    path = Path(path)
    if not path.exists():
        return path
    for suffix in range(2, 10000):
        candidate = path.with_name(f"{path.stem}_{suffix}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("Could not find an unused export filename.")
