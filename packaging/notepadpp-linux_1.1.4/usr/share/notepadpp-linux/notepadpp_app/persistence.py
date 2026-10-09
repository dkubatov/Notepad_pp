"""Validated persistence for editor settings and open-tab sessions."""

from __future__ import annotations

import codecs
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .file_io import write_text_atomically

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {"word_wrap": False, "dark_theme": True}


@dataclass(frozen=True)
class SessionTab:
    path: Optional[str]
    encoding: str
    content: str = ""


@dataclass(frozen=True)
class SessionState:
    tabs: list[SessionTab]
    active: int


def load_settings(path: Path) -> dict[str, bool]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("settings root must be an object")
        settings = DEFAULT_SETTINGS.copy()
        for key in settings:
            value = payload.get(key, settings[key])
            if not isinstance(value, bool):
                raise ValueError(f"setting {key!r} must be boolean")
            settings[key] = value
        return settings
    except FileNotFoundError:
        return DEFAULT_SETTINGS.copy()
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Cannot load settings from %s: %s", path, exc)
        return DEFAULT_SETTINGS.copy()


def save_settings(path: Path, settings: dict[str, bool]) -> None:
    payload = {key: bool(settings[key]) for key in DEFAULT_SETTINGS}
    write_text_atomically(path, json.dumps(payload), "utf-8")


def load_session(path: Path) -> Optional[SessionState]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        logger.warning("Cannot load session from %s: %s", path, exc)
        return None

    try:
        if not isinstance(payload, dict):
            raise ValueError("session root must be an object")
        raw_tabs = payload.get("tabs")
        active = payload.get("active", 0)
        if not isinstance(raw_tabs, list):
            raise ValueError("session tabs must be a list")
        if not isinstance(active, int) or isinstance(active, bool):
            raise ValueError("active tab index must be an integer")

        tabs = []
        for index, item in enumerate(raw_tabs):
            if not isinstance(item, dict):
                raise ValueError(f"tab {index} must be an object")
            tab_path = item.get("path")
            encoding = item.get("encoding", "utf-8")
            content = item.get("content", "")
            if tab_path is not None and not isinstance(tab_path, str):
                raise ValueError(f"tab {index} path must be a string or null")
            if isinstance(tab_path, str) and "\0" in tab_path:
                raise ValueError(f"tab {index} path contains a null character")
            if not isinstance(encoding, str):
                raise ValueError(f"tab {index} encoding must be a string")
            try:
                codecs.lookup(encoding)
            except LookupError as exc:
                raise ValueError(f"tab {index} has unknown encoding {encoding!r}") from exc
            if tab_path is None and not isinstance(content, str):
                raise ValueError(f"tab {index} content must be a string")
            tabs.append(SessionTab(tab_path, encoding, content if tab_path is None else ""))
        return SessionState(tabs, active)
    except ValueError as exc:
        logger.warning("Ignoring invalid session at %s: %s", path, exc)
        return None


def save_session(path: Path, session: SessionState) -> None:
    payload = {
        "tabs": [
            {
                "path": tab.path,
                "encoding": tab.encoding,
                **({"content": tab.content} if tab.path is None else {}),
            }
            for tab in session.tabs
        ],
        "active": session.active,
    }
    write_text_atomically(path, json.dumps(payload, ensure_ascii=False), "utf-8")
