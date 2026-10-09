"""File decoding and durable text-file writes."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from .config import ENCODINGS


def read_text(path: Path, encoding: str, *, replace_invalid: bool = False) -> str:
    data = path.read_bytes()
    errors = "replace" if replace_invalid else "strict"
    return data.decode(encoding, errors=errors).replace("\r\n", "\n").replace("\r", "\n")


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
    existing_stat = None
    try:
        existing_stat = target.stat()
    except FileNotFoundError:
        pass

    try:
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
    except PermissionError:
        if existing_stat is None:
            raise
        with target.open("w", encoding=encoding) as stream:
            stream.write(text)
        return

    temporary_path = Path(temporary_name)
    try:
        if existing_stat is not None:
            try:
                os.fchown(fd, existing_stat.st_uid, existing_stat.st_gid)
                shutil.copystat(target, temporary_path, follow_symlinks=False)
                for name in os.listxattr(target, follow_symlinks=False):
                    value = os.getxattr(target, name, follow_symlinks=False)
                    os.setxattr(temporary_path, name, value, follow_symlinks=False)
            except OSError:
                os.close(fd)
                fd = -1
                temporary_path.unlink(missing_ok=True)
                with target.open("w", encoding=encoding) as stream:
                    stream.write(text)
                return
        with os.fdopen(fd, "w", encoding=encoding, newline="") as stream:
            fd = -1
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, target)
        try:
            directory_fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    except BaseException:
        if fd >= 0:
            os.close(fd)
        temporary_path.unlink(missing_ok=True)
        raise
