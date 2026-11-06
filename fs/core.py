"""Core filesystem operations sandboxed within ROOT_DIR."""

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
from typing import Any

DEFAULT_ROOT_DIR = Path("/data/root")


class FsError(Exception):
    """Base error for filesystem operations."""

    status_code = 400


class BadPathError(FsError):
    """Invalid or out-of-bounds path."""

    status_code = 400


class NotFoundError(FsError):
    """Target file or directory does not exist."""

    status_code = 404


class ConflictError(FsError):
    """Destination already exists."""

    status_code = 409


def list_dir(rel_path: str = "") -> dict[str, Any]:
    """List directory entries sorted with directories first, then alphabetically."""
    base, target = _resolve(rel_path)
    if not target.exists():
        raise NotFoundError(f"path not found: {rel_path}")
    if not target.is_dir():
        raise BadPathError(f"not a directory: {rel_path}")

    entries = []
    for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        stat = item.stat()
        is_dir = item.is_dir()
        entries.append(
            {
                "name": item.name,
                "path": _rel_posix(base, item),
                "type": "dir" if is_dir else "file",
                "size": None if is_dir else stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
        )

    return {"path": _rel_posix(base, target), "entries": entries}


def resolve_download(rel_path: str) -> Path:
    """Resolve and validate a file path for download."""
    _, target = _resolve(rel_path)
    if not target.exists() or not target.is_file():
        raise NotFoundError(f"file not found: {rel_path}")
    return target


def upload_files(
    rel_dir: str,
    files: list[Any],
    overwrite: bool = False,
    mkdir: bool = False,
) -> list[str]:
    """Save uploaded file objects into rel_dir and return their relative paths."""
    base, target_dir = _resolve(rel_dir)
    if mkdir:
        target_dir.mkdir(parents=True, exist_ok=True)
    if not target_dir.exists() or not target_dir.is_dir():
        raise NotFoundError(f"directory not found: {rel_dir}")

    valid_files = [f for f in files if f and getattr(f, "filename", None)]
    if not valid_files:
        raise BadPathError("no file uploaded")

    destinations = []
    for f in valid_files:
        name = f.filename.strip()
        if "/" in name or "\\" in name or name in ("", ".", ".."):
            raise BadPathError(f"invalid filename: {name!r}")
        dest = (target_dir / name).resolve()
        if not dest.is_relative_to(base):
            raise BadPathError("path escapes root directory")
        if dest.exists() and not overwrite:
            raise ConflictError(f"{name!r} already exists")
        if dest.exists() and dest.is_dir():
            raise ConflictError(f"{name!r} is a directory")
        destinations.append((f, dest))

    uploaded = []
    for f, dest in destinations:
        f.save(dest)
        uploaded.append(_rel_posix(base, dest))

    return uploaded


def rename_entry(src_rel: str, new_name: str) -> dict[str, str]:
    """Rename an entry in place or move it to a new relative path inside ROOT_DIR."""
    src_arg = (src_rel or "").strip()
    new_arg = (new_name or "").strip()
    if not src_arg or not new_arg:
        raise BadPathError("both 'path' and 'new_name' are required")

    base, src = _resolve(src_arg)
    if src == base:
        raise BadPathError("cannot rename root directory")
    if not src.exists():
        raise NotFoundError(f"path not found: {src_arg}")

    if "/" in new_arg or "\\" in new_arg:
        _, dst = _resolve(new_arg)
    else:
        if new_arg in (".", ".."):
            raise BadPathError(f"invalid name: {new_arg!r}")
        dst = (src.parent / new_arg).resolve()
        if not dst.is_relative_to(base):
            raise BadPathError("path escapes root directory")

    if dst == base:
        raise BadPathError("cannot overwrite root directory")
    if dst.exists():
        raise ConflictError(f"destination already exists: {_rel_posix(base, dst)}")
    if not dst.parent.exists():
        raise NotFoundError(f"destination directory does not exist: {_rel_posix(base, dst.parent)}")

    src.rename(dst)
    return {"from": _rel_posix(base, src), "path": _rel_posix(base, dst)}


def delete_entry(rel_path: str) -> str:
    """Delete a file or directory tree inside ROOT_DIR and return its relative path."""
    rel_arg = (rel_path or "").strip()
    if not rel_arg:
        raise BadPathError("missing 'path'")

    base, target = _resolve(rel_arg)
    if target == base:
        raise BadPathError("cannot delete root directory")
    if not target.exists():
        raise NotFoundError(f"path not found: {rel_arg}")

    rel_deleted = _rel_posix(base, target)
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()

    return rel_deleted


def make_dir(rel_path: str) -> str:
    """Create a directory inside ROOT_DIR and return its relative path."""
    rel_arg = (rel_path or "").strip()
    if not rel_arg:
        raise BadPathError("missing 'path'")

    base, target = _resolve(rel_arg)
    if target == base:
        raise ConflictError("root already exists")
    if target.exists():
        raise ConflictError(f"already exists: {rel_arg}")

    target.mkdir(parents=True, exist_ok=False)
    return _rel_posix(base, target)


def root_dir() -> Path:
    """Return the resolved root directory served by the filesystem service."""
    return Path(os.environ.get("ROOT_DIR", DEFAULT_ROOT_DIR)).resolve()


def _resolve(rel_path: str) -> tuple[Path, Path]:
    base = root_dir()
    cleaned = (rel_path or "").strip().lstrip("/\\")
    if cleaned in ("", "."):
        return base, base
    target = (base / cleaned).resolve()
    if not target.is_relative_to(base):
        raise BadPathError("path escapes root directory")
    return base, target


def _rel_posix(base: Path, target: Path) -> str:
    rel = target.relative_to(base)
    return "" if str(rel) == "." else rel.as_posix()
