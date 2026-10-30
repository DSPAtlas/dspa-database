"""Case-insensitive lookup for experiment files exported on Windows."""
from pathlib import Path


def find_file(folder: Path, name: str) -> Path | None:
    """Return the unique matching file, preserving its actual filename."""
    matches = sorted(
        path for path in folder.iterdir()
        if path.name.casefold() == name.casefold() and path.is_file()
    )
    if len(matches) > 1:
        names = ", ".join(path.name for path in matches)
        raise ValueError(f"Ambiguous filename {name!r} in {folder}: {names}")
    return matches[0] if matches else None
