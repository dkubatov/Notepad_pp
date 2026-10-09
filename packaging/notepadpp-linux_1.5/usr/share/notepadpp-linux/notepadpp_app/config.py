from __future__ import annotations

from pathlib import Path


APP_ID = "org.notepadpp.linux"
SCRIPT_DIR = Path(__file__).resolve().parent.parent
ICON_PATH = SCRIPT_DIR / "icon" / "notepadpp_icon_256_transparent.png"
CONFIG_DIR = Path.home() / ".config" / "notepadpp-linux"
SESSION_FILE = CONFIG_DIR / "session.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

ENCODINGS = [
    ("utf-8", "UTF-8"),
    ("utf-16", "UTF-16"),
    ("cp1251", "Windows-1251"),
    ("cp1252", "Windows-1252"),
    ("cp866", "DOS CP866"),
    ("koi8-r", "KOI8-R (Linux)"),
    ("iso-8859-1", "ISO-8859-1 (Latin-1)"),
]

LANG_EXTENSIONS: dict[str, str] = {
    ".txt": "text",
    ".csv": "csv",
    ".md": "markdown",
    ".xml": "xml",
    ".json": "json",
    ".os": "1c-ent",
    ".bsl": "1c-ent",
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".html": "html",
    ".css": "css",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "cpphdr",
    ".java": "java",
    ".sh": "sh",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sql": "sql",
    ".go": "go",
    ".rs": "rust",
}

LANG_LABELS: dict[str, str] = {
    "text": "Plain Text",
    "csv": "CSV",
    "markdown": "Markdown",
    "xml": "XML",
    "json": "JSON",
    "1c-ent": "1C Enterprise",
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "html": "HTML",
    "css": "CSS",
    "c": "C",
    "cpp": "C++",
    "cpphdr": "C/C++ Header",
    "java": "Java",
    "sh": "Shell",
    "yaml": "YAML",
    "sql": "SQL",
    "go": "Go",
    "rust": "Rust",
}

LANGUAGE_MENU_ITEMS: list[tuple[str, str]] = [
    ("Plain Text", "text"),
    ("CSV", "csv"),
    ("Markdown", "markdown"),
    ("XML", "xml"),
    ("JSON", "json"),
    ("1C Enterprise", "1c-ent"),
    ("Python", "python"),
    ("JavaScript", "javascript"),
    ("TypeScript", "typescript"),
    ("HTML", "html"),
    ("CSS", "css"),
    ("C", "c"),
    ("C++", "cpp"),
    ("C/C++ Header", "cpphdr"),
    ("Java", "java"),
    ("Shell", "sh"),
    ("YAML", "yaml"),
    ("SQL", "sql"),
    ("Go", "go"),
    ("Rust", "rust"),
]

LANG_EXT_TO_EXTENSION: dict[str, str] = {v: k for k, v in LANG_EXTENSIONS.items()}
LANG_EXT_TO_EXTENSION.update(
    {
        lang_id: f".{lang_id}"
        for _label, lang_id in LANGUAGE_MENU_ITEMS
        if lang_id not in LANG_EXT_TO_EXTENSION
    }
)
LANG_EXT_TO_EXTENSION.update(
    {
        "text": ".txt",
        "1c-ent": ".bsl",
        "cpphdr": ".h",
        "javascript": ".js",
        "typescript": ".ts",
        "markdown": ".md",
    }
)
