"""File decoding and durable text-file writes."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from .config import ENCODINGS


def read_text(path: Path, encoding: str, *, replace_invalid: bool = False) -> str:
    data = path.read_bytes()
    errors = "replace" if replace_invalid else "strict"
    return data.decode(encoding, errors=errors)


def read_text_for_display(path: Path, encoding: str) -> str:
    try:
        return read_text(path, encoding)
    except UnicodeError:
        return read_text(path, encoding, replace_invalid=True)


def read_text_with_detected_encoding(path: Path) -> tuple[str, str]:
    seen: set[str] = set()
    for encoding, _label in ENCODINGS:
        if encoding in seen:
            continue
        seen.add(encoding)
        try:
            return read_text(path, encoding), encoding
        except UnicodeError:
            continue
    return read_text(path, "utf-8", replace_invalid=True), "utf-8"


def write_text_atomically(path: Path, text: str, encoding: str) -> None:
    target = path.resolve()
    existing_mode = None
    try:
        existing_mode = stat.S_IMODE(target.stat().st_mode)
    except FileNotFoundError:
        pass

    current_umask = os.umask(0)
    os.umask(current_umask)
    mode = existing_mode if existing_mode is not None else 0o666 & ~current_umask

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding=encoding, newline="") as stream:
            fd = -1
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, target)
    except BaseException:
        if fd >= 0:
            os.close(fd)
        temporary_path.unlink(missing_ok=True)
        raise
