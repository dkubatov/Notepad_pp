"""GTK application implementation for Notepad Light."""

from __future__ import annotations

import json
import re
import sys
import webbrowser
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkSource", "3.0")

from gi.repository import Gdk, Gio, GLib, Gtk, GtkSource, Pango

from .config import (
    APP_ID,
    CONFIG_DIR,
    ENCODINGS,
    ICON_PATH,
    LANG_EXTENSIONS,
    LANG_EXT_TO_EXTENSION,
    LANG_LABELS,
    LANGUAGE_MENU_ITEMS,
    SCRIPT_DIR,
    SESSION_FILE,
    SETTINGS_FILE,
)

URL_PATTERN = re.compile(r"(https?://[^\s<>\"]+)")
EDITOR_THEME_PROVIDER = Gtk.CssProvider()


def _read_text_for_display(path: Path, encoding: str) -> str:
    data = path.read_bytes()
    try:
        return data.decode(encoding)
    except UnicodeError:
        return data.decode(encoding, errors="replace")


def _apply_editor_theme_css(dark: bool) -> None:
    css = (
        b"""
        textview.notepad-editor,
        textview.notepad-editor text {
            background-color: #1e1e1e;
            color: #d4d4d4;
            caret-color: #ffffff;
            font: 11pt Monospace;
        }
        textview.notepad-editor selection {
            background-color: #264f78;
            color: #ffffff;
        }
        """
        if dark
        else b"""
        textview.notepad-editor,
        textview.notepad-editor text {
            background-color: #ffffff;
            color: #202124;
            caret-color: #000000;
            font: 11pt Monospace;
        }
        textview.notepad-editor selection {
            background-color: #b7d7ff;
            color: #000000;
        }
        """
    )
    EDITOR_THEME_PROVIDER.load_from_data(css)
    screen = Gdk.Screen.get_default()
    if screen:
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            EDITOR_THEME_PROVIDER,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )


def _install_warning_filters() -> None:
    def _filter_handler(_domain: str, _level: GLib.LogLevelFlags, message: str) -> None:
        if "could not load style scheme file" in message and "missing 'version' attribute" in message:
            return
        sys.stderr.write(f"GtkSourceView-WARNING: {message}\n")

    GLib.log_set_handler(
        "GtkSourceView",
        GLib.LogLevelFlags.LEVEL_WARNING,
        _filter_handler,
    )


class EditorTab(Gtk.Box):

    @staticmethod
    def _pick_style_scheme() -> Optional[GtkSource.StyleScheme]:
        """Return a style scheme matching the current dark-theme preference.
        Falls back to 'oblivion' (dark) when gtk-application-prefer-dark-theme
        is active, otherwise 'classic' (light).  If neither scheme is available
        returns None so GtkSourceView uses its default."""
        dark = False
        try:
            settings = Gtk.Settings.get_default()
            if settings:
                dark = settings.get_property("gtk-application-prefer-dark-theme")
        except Exception:
            pass
        scheme_id = "oblivion" if dark else "classic"
        mgr = GtkSource.StyleSchemeManager.get_default()
        scheme = mgr.get_scheme(scheme_id)
        if scheme is not None:
            return scheme
        # fallback — try the other one
        alt = "classic" if dark else "oblivion"
        return mgr.get_scheme(alt)

    def _apply_style_scheme(self) -> None:
        """Set the buffer's style scheme according to the current theme preference."""
        scheme = self._pick_style_scheme()
        if scheme is not None:
            self.buffer.set_style_scheme(scheme)

    def __init__(
        self, path: Optional[Path] = None, content: str = "", encoding: str = "utf-8",
        language_id: str = "text"
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.path = path
        self.search_mark = None
        self.encoding = encoding
        self._language_id = language_id
        self._link_refresh_source_id = 0

        self.buffer = GtkSource.Buffer()
        self.buffer.set_highlight_syntax(True)
        self.buffer.set_highlight_matching_brackets(True)
        self.buffer.connect("changed", self._on_buffer_changed)
        self.link_tag = self.buffer.create_tag(
            "link",
            foreground="#4a90e2",
            underline=Pango.Underline.SINGLE,
        )

        self.view = GtkSource.View.new_with_buffer(self.buffer)
        self.view.set_show_line_numbers(True)
        self.view.set_monospace(True)
        self.view.set_tab_width(4)
        self.view.set_insert_spaces_instead_of_tabs(True)
        self.view.get_style_context().add_class("notepad-editor")
        self.view.add_events(
            Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK
        )
        self.view.connect("button-release-event", self._on_view_click)
        self.view.connect("motion-notify-event", self._on_view_motion)
        self.view.connect("leave-notify-event", self._on_view_leave)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.add(self.view)
        self.pack_start(self.scrolled, True, True, 0)

        self.buffer.set_text(content)
        self.buffer.set_modified(False)

        if self.path:
            self._language_id = LANG_EXTENSIONS.get(self.path.suffix.lower(), "text")
        self._apply_language()
        # Apply style scheme AFTER setting the language, because GtkSourceView
        # may reset the scheme when set_language() is called.
        self._apply_style_scheme()
        self._refresh_links()

        self.show_all()

    @property
    def modified(self) -> bool:
        return self.buffer.get_modified()

    def _on_buffer_changed(self, _buffer: GtkSource.Buffer) -> None:
        self._schedule_link_refresh()

    def _schedule_link_refresh(self) -> None:
        if self._link_refresh_source_id:
            GLib.source_remove(self._link_refresh_source_id)
        self._link_refresh_source_id = GLib.timeout_add(200, self._refresh_links_debounced)

    def _refresh_links_debounced(self) -> bool:
        self._link_refresh_source_id = 0
        self._refresh_links()
        return False

    def _refresh_links(self) -> None:
        start, end = self.buffer.get_bounds()
        self.buffer.remove_tag(self.link_tag, start, end)
        text = self.buffer.get_text(start, end, True)
        for match in URL_PATTERN.finditer(text):
            match_start = self.buffer.get_iter_at_offset(match.start())
            match_end = self.buffer.get_iter_at_offset(match.end())
            self.buffer.apply_tag(self.link_tag, match_start, match_end)

    def _on_view_click(self, _view: Gtk.Widget, event: Gdk.EventButton) -> bool:
        if event.button != 1:
            return False
        if not (event.state & Gdk.ModifierType.CONTROL_MASK):
            return False
        x, y = self.view.window_to_buffer_coords(
            Gtk.TextWindowType.TEXT, int(event.x), int(event.y)
        )
        iter_at_click = self._iter_at_location(x, y)
        if not iter_at_click:
            return False
        if self._iter_has_link(iter_at_click):
            url = self._url_at_iter(iter_at_click)
            if url:
                webbrowser.open(url)
                return True
        return False

    def _on_view_motion(self, _view: Gtk.Widget, event: Gdk.EventMotion) -> bool:
        x, y = self.view.window_to_buffer_coords(
            Gtk.TextWindowType.TEXT, int(event.x), int(event.y)
        )
        iter_at_pos = self._iter_at_location(x, y)
        text_window = self.view.get_window(Gtk.TextWindowType.TEXT)
        if not text_window:
            return False
        if iter_at_pos and self._iter_has_link(iter_at_pos):
            cursor = Gdk.Cursor.new_for_display(
                self.view.get_display(), Gdk.CursorType.HAND2
            )
        else:
            cursor = Gdk.Cursor.new_for_display(
                self.view.get_display(), Gdk.CursorType.XTERM
            )
        text_window.set_cursor(cursor)
        return False

    def _on_view_leave(self, _view: Gtk.Widget, _event: Gdk.EventCrossing) -> bool:
        text_window = self.view.get_window(Gtk.TextWindowType.TEXT)
        if text_window:
            text_window.set_cursor(
                Gdk.Cursor.new_for_display(self.view.get_display(), Gdk.CursorType.XTERM)
            )
        return False

    def _iter_at_location(self, x: int, y: int) -> Optional[Gtk.TextIter]:
        result = self.view.get_iter_at_location(x, y)
        if isinstance(result, tuple):
            for item in result:
                if isinstance(item, Gtk.TextIter):
                    return item
            return None
        return result

    def _iter_has_link(self, iter_: Gtk.TextIter) -> bool:
        for tag in iter_.get_tags():
            if tag == self.link_tag or tag.get_property("name") == "link":
                return True
        return False

    def _url_at_iter(self, iter_: Gtk.TextIter) -> Optional[str]:
        start = iter_.copy()
        end = iter_.copy()
        while start.backward_char():
            if start.get_char().isspace():
                start.forward_char()
                break
        while end.forward_char():
            if end.get_char().isspace():
                break
        candidate = self.buffer.get_text(start, end, True).strip()
        matched = URL_PATTERN.search(candidate)
        return matched.group(0) if matched else None

    def _set_language_from_path(self, path: Path) -> None:
        self._language_id = LANG_EXTENSIONS.get(path.suffix.lower(), "text")
        self._apply_language()

    def set_language(self, language_id: str) -> None:
        """Set syntax highlighting language by language id (e.g. 'text', 'json', '1c-ent')."""
        self._language_id = language_id
        self._apply_language()
        # Re-apply style scheme after language change (set_language can reset it)
        self._apply_style_scheme()

    @staticmethod
    def _setup_language_search_path() -> None:
        """Register the custom languages/ directory so GtkSource can find .lang files."""
        lang_manager = GtkSource.LanguageManager.get_default()
        existing = list(lang_manager.get_search_path())
        langs_dir = str(SCRIPT_DIR / "languages")
        if langs_dir not in existing:
            existing.insert(0, langs_dir)
            lang_manager.set_search_path(existing)

    def _apply_language(self) -> None:
        """Apply the language identified by self._language_id to the buffer."""
        lang_manager = GtkSource.LanguageManager.get_default()

        # Plain text — no highlighting
        if self._language_id == "text":
            self.buffer.set_highlight_syntax(False)
            self.buffer.set_language(None)
            return

        # Try to load the language from GtkSource (includes custom csv, 1c-ent)
        source_lang = lang_manager.get_language(self._language_id)
        if source_lang:
            self.buffer.set_highlight_syntax(True)
            self.buffer.set_language(source_lang)
        else:
            # Unknown language id — fall back to no highlighting
            self.buffer.set_highlight_syntax(False)
            self.buffer.set_language(None)

    def load_file(self, path: Path) -> None:
        text = _read_text_for_display(path, self.encoding)
        self.path = path
        self.buffer.set_text(text)
        self.buffer.set_modified(False)
        self._set_language_from_path(path)

    def reload_with_encoding(self, encoding: str) -> None:
        if not self.path:
            self.set_encoding(encoding)
            return
        text = _read_text_for_display(self.path, encoding)
        self.encoding = encoding
        self.buffer.set_text(text)
        self.buffer.set_modified(False)
        self._set_language_from_path(self.path)
        self._apply_style_scheme()
        self._refresh_links()

    def save(self) -> bool:
        if not self.path:
            return False
        start, end = self.buffer.get_bounds()
        text = self.buffer.get_text(start, end, True)
        self.path.write_text(text, encoding=self.encoding)
        self.buffer.set_modified(False)
        return True

    def save_as(self, path: Path) -> bool:
        self.path = path
        self._set_language_from_path(path)
        return self.save()

    def set_encoding(self, encoding: str) -> None:
        if self.encoding == encoding:
            return
        self.encoding = encoding
        self.buffer.set_modified(True)

    def get_title(self) -> str:
        base = self.path.name if self.path else "Untitled"
        return f"* {base}" if self.modified else base

    def cursor_position(self) -> tuple[int, int]:
        insert_mark = self.buffer.get_insert()
        iter_ = self.buffer.get_iter_at_mark(insert_mark)
        return iter_.get_line() + 1, iter_.get_line_offset() + 1

    def find_next(self, text: str, case_sensitive: bool) -> bool:
        if not text:
            return False
        flags = 0 if case_sensitive else Gtk.TextSearchFlags.CASE_INSENSITIVE
        start = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        match = start.forward_search(text, flags, None)
        if not match:
            start = self.buffer.get_start_iter()
            match = start.forward_search(text, flags, None)
        if match:
            match_start, match_end = match
            self.buffer.select_range(match_start, match_end)
            self.view.scroll_to_iter(match_start, 0.2, True, 0.0, 0.2)
            return True
        return False

    def replace_selection(self, replacement: str) -> bool:
        if not self.buffer.get_has_selection():
            return False
        start, end = self.buffer.get_selection_bounds()
        self.buffer.begin_user_action()
        self.buffer.delete(start, end)
        self.buffer.insert(start, replacement)
        self.buffer.end_user_action()
        return True


class FindReplaceDialog(Gtk.Dialog):
    def __init__(self, parent: Gtk.Window):
        super().__init__(title="Find / Replace", transient_for=parent, modal=False)
        self.set_default_size(420, 140)
        self.add_buttons("Close", Gtk.ResponseType.CLOSE)

        area = self.get_content_area()
        grid = Gtk.Grid(column_spacing=8, row_spacing=8, margin=12)
        area.add(grid)

        self.find_entry = Gtk.Entry()
        self.replace_entry = Gtk.Entry()
        self.case_check = Gtk.CheckButton(label="Case sensitive")
        self.find_btn = Gtk.Button(label="Find next")
        self.replace_btn = Gtk.Button(label="Replace")

        grid.attach(Gtk.Label(label="Find:"), 0, 0, 1, 1)
        grid.attach(self.find_entry, 1, 0, 2, 1)
        grid.attach(Gtk.Label(label="Replace with:"), 0, 1, 1, 1)
        grid.attach(self.replace_entry, 1, 1, 2, 1)
        grid.attach(self.case_check, 1, 2, 1, 1)
        grid.attach(self.find_btn, 1, 3, 1, 1)
        grid.attach(self.replace_btn, 2, 3, 1, 1)
        self.show_all()


class NotepadLinuxWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application):
        super().__init__(application=app, title="Notepad light")
        self.set_default_size(1024, 720)

        EditorTab._setup_language_search_path()

        self.find_dialog: Optional[FindReplaceDialog] = None
        self._updating_encoding_menu = False
        self.encoding_menu_items: dict[str, Gtk.RadioMenuItem] = {}
        self.encoding_menu_handlers: dict[str, int] = {}
        self._updating_language_menu = False
        self.language_menu_items: dict[str, Gtk.RadioMenuItem] = {}
        self.language_menu_handlers: dict[str, int] = {}
        self._ui_sync_source_id = 0
        self.status = Gtk.Statusbar()
        self.status_ctx = self.status.get_context_id("cursor")

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root)

        root.pack_start(self._build_menu_bar(), False, False, 0)

        tab_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        self.new_tab_btn = Gtk.Button(label="+")
        self.new_tab_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.new_tab_btn.set_tooltip_text("New tab")
        self.new_tab_btn.set_focus_on_click(False)
        self.new_tab_btn.connect("clicked", lambda *_: self._new_tab())
        tab_controls.pack_end(self.new_tab_btn, False, False, 0)
        root.pack_start(tab_controls, False, False, 0)

        self.notebook = Gtk.Notebook()
        self.notebook.set_scrollable(True)
        self.notebook.connect("switch-page", self._on_switch_page)
        root.pack_start(self.notebook, True, True, 0)
        root.pack_start(self.status, False, False, 0)

        if not self._load_session():
            self._new_tab()
        # Apply saved wrap mode to all tabs
        if hasattr(self, "_wrap_item") and self._wrap_item.get_active():
            for i in range(self.notebook.get_n_pages()):
                tab = self.notebook.get_nth_page(i)
                if isinstance(tab, EditorTab):
                    tab.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._update_status()
        self.show_all()

    def _load_settings(self) -> dict:
        """Load persisted settings (word wrap, dark theme)."""
        try:
            if SETTINGS_FILE.exists():
                return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"word_wrap": False, "dark_theme": True}

    def _save_settings(self) -> None:
        """Persist current settings (word wrap, dark theme)."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            payload = {
                "word_wrap": self._wrap_item.get_active() if hasattr(self, "_wrap_item") else False,
                "dark_theme": self._dark_item.get_active() if hasattr(self, "_dark_item") else True,
            }
            self._write_json_atomic(SETTINGS_FILE, payload)
        except Exception:
            pass

    def _build_menu_bar(self) -> Gtk.MenuBar:
        menu_bar = Gtk.MenuBar()

        file_menu = Gtk.Menu()
        file_item = Gtk.MenuItem(label="File")
        file_item.set_submenu(file_menu)
        menu_bar.append(file_item)

        edit_menu = Gtk.Menu()
        edit_item = Gtk.MenuItem(label="Edit")
        edit_item.set_submenu(edit_menu)
        menu_bar.append(edit_item)

        view_menu = Gtk.Menu()
        view_item = Gtk.MenuItem(label="View")
        view_item.set_submenu(view_menu)
        menu_bar.append(view_item)

        encoding_menu = Gtk.Menu()
        encoding_item = Gtk.MenuItem(label="Encoding")
        encoding_item.set_submenu(encoding_menu)
        menu_bar.append(encoding_item)

        syntax_menu = Gtk.Menu()
        syntax_item = Gtk.MenuItem(label="Syntax Highlight")
        syntax_item.set_submenu(syntax_menu)
        menu_bar.append(syntax_item)

        self._append_menu_item(file_menu, "New", self._new_tab, "<Ctrl>N")
        self._append_menu_item(file_menu, "Open...", self._open_file_dialog, "<Ctrl>O")
        self._append_menu_item(file_menu, "Save", self._save_current, "<Ctrl>S")
        self._append_menu_item(file_menu, "Save As...", self._save_as_current, "<Ctrl><Shift>S")
        self._append_menu_item(file_menu, "Close Tab", self._close_current_tab, "<Ctrl>W")
        self._append_menu_item(file_menu, "Quit", self._on_quit, "<Ctrl>Q")

        self._append_menu_item(edit_menu, "Find / Replace", self._open_find_dialog, "<Ctrl>F")
        self._append_menu_item(edit_menu, "Undo", self._undo, "<Ctrl>Z")
        self._append_menu_item(edit_menu, "Redo", self._redo, "<Ctrl>Y")
        self._append_menu_item(edit_menu, "Duplicate Line", self._duplicate_line, "<Ctrl>D")

        saved = self._load_settings()

        wrap_item = Gtk.CheckMenuItem(label="Word Wrap")
        wrap_item.set_active(saved.get("word_wrap", False))
        wrap_item.connect("toggled", self._toggle_wrap)
        view_menu.append(wrap_item)
        self._wrap_item = wrap_item

        dark_item = Gtk.CheckMenuItem(label="Dark Theme")
        dark_item.set_active(saved.get("dark_theme", True))
        dark_item.connect("toggled", self._toggle_dark_theme)
        view_menu.append(dark_item)
        self._dark_item = dark_item

        group: Optional[Gtk.RadioMenuItem] = None
        for encoding, label in ENCODINGS:
            if group is None:
                item = Gtk.RadioMenuItem.new_with_label(None, label)
                group = item
            else:
                item = Gtk.RadioMenuItem.new_with_label_from_widget(group, label)
            handler_id = item.connect("toggled", self._on_encoding_selected, encoding)
            encoding_menu.append(item)
            self.encoding_menu_items[encoding] = item
            self.encoding_menu_handlers[encoding] = handler_id

        lang_group: Optional[Gtk.RadioMenuItem] = None
        for label, lang_id in LANGUAGE_MENU_ITEMS:
            if lang_group is None:
                item = Gtk.RadioMenuItem.new_with_label(None, label)
                lang_group = item
            else:
                item = Gtk.RadioMenuItem.new_with_label_from_widget(lang_group, label)
            handler_id = item.connect("toggled", self._on_language_selected, lang_id)
            syntax_menu.append(item)
            self.language_menu_items[lang_id] = item
            self.language_menu_handlers[lang_id] = handler_id

        self._toggle_dark_theme(dark_item)
        return menu_bar

    def _append_menu_item(self, menu: Gtk.Menu, label: str, callback, accel: str) -> None:
        item = Gtk.MenuItem(label=label)
        item.connect("activate", lambda *_args: callback())
        menu.append(item)

        key, mod = Gtk.accelerator_parse(accel)
        item.add_accelerator("activate", self._accel_group(), key, mod, Gtk.AccelFlags.VISIBLE)

    def _accel_group(self) -> Gtk.AccelGroup:
        if not hasattr(self, "_accels"):
            self._accels = Gtk.AccelGroup()
            self.add_accel_group(self._accels)
        return self._accels

    def _current_tab(self) -> Optional[EditorTab]:
        idx = self.notebook.get_current_page()
        if idx < 0:
            return None
        widget = self.notebook.get_nth_page(idx)
        return widget if isinstance(widget, EditorTab) else None

    def _iter_tabs(self):
        for i in range(self.notebook.get_n_pages()):
            tab = self.notebook.get_nth_page(i)
            if isinstance(tab, EditorTab):
                yield tab

    def _resolve_path(self, path: Path) -> Path:
        try:
            return path.expanduser().resolve()
        except OSError:
            return path.expanduser().absolute()

    def _find_tab_by_path(self, path: Path) -> Optional[EditorTab]:
        resolved = self._resolve_path(path)
        for tab in self._iter_tabs():
            if tab.path and self._resolve_path(tab.path) == resolved:
                return tab
        return None

    def _add_tab(self, tab: EditorTab) -> None:
        tab.view.connect("move-cursor", lambda *_: self._update_status())
        tab.view.connect("button-release-event", lambda *_: self._update_status() or False)
        tab.buffer.connect("changed", lambda *_: self._refresh_tab_titles())

        header = self._build_tab_header(tab)
        self.notebook.append_page(tab, header)
        self.notebook.set_tab_reorderable(tab, True)
        self.notebook.set_tab_detachable(tab, False)
        tab.show_all()
        header.show_all()

    def _build_tab_header(self, tab: EditorTab) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_click_area = Gtk.EventBox()
        title_click_area.set_visible_window(False)
        title_click_area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        title_click_area.connect("button-press-event", self._on_tab_header_click, tab)
        title = Gtk.Label(label=tab.get_title())
        title.set_xalign(0.0)
        title_click_area.add(title)
        close_btn = Gtk.Button.new_from_icon_name("window-close", Gtk.IconSize.MENU)
        close_btn.set_relief(Gtk.ReliefStyle.NONE)
        close_btn.set_focus_on_click(False)
        close_btn.connect("clicked", lambda *_: self._close_tab(tab))
        box.pack_start(title_click_area, True, True, 0)
        box.pack_start(close_btn, False, False, 0)
        box.show_all()
        return box

    def _on_tab_header_click(
        self,
        _widget: Gtk.Widget,
        event: Gdk.EventButton,
        tab: EditorTab,
    ) -> bool:
        if event.button != 1:
            return False
        page = self.notebook.page_num(tab)
        if page >= 0:
            self.notebook.set_current_page(page)
            self._schedule_current_tab_ui_sync()
            return True
        return False

    def _new_tab(self) -> None:
        tab = EditorTab()
        self._add_tab(tab)
        self.notebook.set_current_page(self.notebook.page_num(tab))
        self._refresh_tab_titles()
        self._update_status()

    def _read_file_with_detected_encoding(self, path: Path) -> tuple[str, str]:
        candidates = [enc for enc, _ in ENCODINGS]
        seen = set()
        ordered_candidates = []
        for enc in candidates:
            if enc not in seen:
                ordered_candidates.append(enc)
                seen.add(enc)
        for encoding in ordered_candidates:
            try:
                return path.read_text(encoding=encoding), encoding
            except UnicodeDecodeError:
                continue
        return path.read_text(encoding="utf-8", errors="replace"), "utf-8"

    def open_file(self, path: Path) -> None:
        path = self._resolve_path(path)
        existing = self._find_tab_by_path(path)
        if existing:
            self.notebook.set_current_page(self.notebook.page_num(existing))
            self._sync_encoding_menu_from_current_tab()
            self._sync_language_menu_from_current_tab()
            self._update_status()
            return
        content, encoding = self._read_file_with_detected_encoding(path)
        tab = EditorTab(path=path, content=content, encoding=encoding)
        self._add_tab(tab)
        self.notebook.set_current_page(self.notebook.page_num(tab))
        self._refresh_tab_titles()
        self._sync_encoding_menu_from_current_tab()
        self._sync_language_menu_from_current_tab()
        self._update_status()

    def open_files(self, paths: list[Path]) -> None:
        for path in paths:
            try:
                self.open_file(path)
            except Exception as exc:
                self._error_dialog(f"Cannot open file '{path}':\n{exc}")
        self.present()

    def _open_file_dialog(self) -> None:
        dialog = Gtk.FileChooserDialog(
            title="Open file",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Open", Gtk.ResponseType.OK)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            path = Path(dialog.get_filename())
            self.open_files([path])
        dialog.destroy()

    def _save_current(self) -> None:
        tab = self._current_tab()
        if not tab:
            return
        self._save_tab(tab)
        self._refresh_tab_titles()
        self._update_status()

    def _save_as_current(self) -> None:
        tab = self._current_tab()
        if not tab:
            return
        self._save_tab_as(tab)
        self._refresh_tab_titles()
        self._update_status()

    def _save_tab(self, tab: EditorTab) -> bool:
        if tab.path:
            try:
                tab.save()
                return True
            except Exception as exc:
                self._error_dialog(f"Save failed:\n{exc}")
                return False
        return self._save_tab_as(tab)

    def _save_tab_as(self, tab: EditorTab) -> bool:
        dialog = Gtk.FileChooserDialog(
            title="Save file",
            parent=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Save", Gtk.ResponseType.OK)
        dialog.set_do_overwrite_confirmation(True)

        # Remove any pre-existing filters (e.g. built-in "All Files") that
        # may show up as blank entries in some GTK themes.
        for existing_filter in dialog.list_filters():
            dialog.remove_filter(existing_filter)

        # Limit the filter dropdown height to match number of items.
        # GTK defaults to ~10 items height which leaves empty space.
        screen = dialog.get_screen()
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(
            b"GtkComboBox { -GtkComboBox-appears-as-list: 1; }"
        )
        Gtk.StyleContext.add_provider_for_screen(
            screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Add file type filters based on supported languages
        lang_filters: list[tuple[str, str, str]] = [
            ("Plain Text", "*.txt", "text"),
            ("CSV", "*.csv", "csv"),
            ("Markdown", "*.md", "markdown"),
            ("XML", "*.xml", "xml"),
            ("JSON", "*.json", "json"),
            ("Python", "*.py", "python"),
            ("JavaScript", "*.js", "javascript"),
            ("TypeScript", "*.ts", "typescript"),
            ("HTML", "*.html", "html"),
            ("CSS", "*.css", "css"),
            ("C", "*.c", "c"),
            ("C++", "*.cpp", "cpp"),
            ("Java", "*.java", "java"),
            ("Shell", "*.sh", "sh"),
            ("1C Enterprise", "*.bsl;*.os", "1c-ent"),
            ("YAML", "*.yaml;*.yml", "yaml"),
            ("SQL", "*.sql", "sql"),
            ("Go", "*.go", "go"),
            ("Rust", "*.rs", "rust"),
            ("All Files", "*.*", ""),
        ]

        current_lang_id = tab._language_id
        # Build a lookup for later matching by filter name
        filter_name_to_lang: dict[str, str] = {}
        default_filter_name = lang_filters[0][0]
        for label, pattern, lang_id in lang_filters:
            name = f"{label} ({pattern})"
            filter_name_to_lang[name] = lang_id
            filt = Gtk.FileFilter()
            filt.set_name(name)
            for pat in pattern.split(";"):
                filt.add_pattern(pat)
            dialog.add_filter(filt)
            if lang_id == current_lang_id:
                default_filter_name = name

        # Set default filter to match current language
        for filt in dialog.list_filters():
            if filt.get_name() == default_filter_name:
                dialog.set_filter(filt)
                break

        # Set initial filename — always use set_current_name so the extension
        # appears exactly as the filter expects, even for already-saved files
        if tab.path:
            base = tab.path.stem  # filename without extension
        else:
            base = "Untitled"
        ext = LANG_EXT_TO_EXTENSION.get(current_lang_id, ".txt")
        dialog.set_current_name(f"{base}{ext}")

        response = dialog.run()
        saved = False
        if response == Gtk.ResponseType.OK:
            path = Path(dialog.get_filename())

            # Force the extension to match the selected filter
            selected_filter = dialog.get_filter()
            if selected_filter:
                lang_id = filter_name_to_lang.get(selected_filter.get_name())
                if lang_id:
                    ext = LANG_EXT_TO_EXTENSION.get(lang_id, ".txt")
                    path = path.with_suffix(ext)

            try:
                tab.save_as(path)
                saved = True
            except Exception as exc:
                self._error_dialog(f"Save failed:\n{exc}")
        dialog.destroy()
        return saved

    def _close_current_tab(self) -> None:
        tab = self._current_tab()
        if not tab:
            return
        self._close_tab(tab)

    def _close_tab(self, tab: EditorTab) -> None:
        if tab.modified and not self._confirm_close_with_save(tab):
            return
        page = self.notebook.page_num(tab)
        if page < 0:
            return
        self.notebook.remove_page(page)
        if self.notebook.get_n_pages() == 0:
            self._new_tab()
        self._refresh_tab_titles()

    def _confirm_close_with_save(self, tab: EditorTab) -> bool:
        tab_title = tab.path.name if tab.path else "Untitled"
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            text=f"Save changes in '{tab_title}'?",
        )
        dialog.format_secondary_text("Your changes will be lost if you don't save them.")
        dialog.add_buttons(
            "Cancel",
            Gtk.ResponseType.CANCEL,
            "Don't Save",
            Gtk.ResponseType.NO,
            "Save",
            Gtk.ResponseType.YES,
        )
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.CANCEL or response == Gtk.ResponseType.DELETE_EVENT:
            return False
        if response == Gtk.ResponseType.NO:
            return True
        return self._save_tab(tab)

    def _open_find_dialog(self) -> None:
        if self.find_dialog is None:
            self.find_dialog = FindReplaceDialog(self)
            self.find_dialog.find_btn.connect("clicked", self._on_find_next)
            self.find_dialog.replace_btn.connect("clicked", self._on_replace)
            self.find_dialog.connect("response", self._on_find_dialog_response)
        self.find_dialog.present()

    def _on_find_dialog_response(self, dialog: Gtk.Dialog, _response_id: int) -> None:
        dialog.hide()

    def _on_find_next(self, *_args) -> None:
        tab = self._current_tab()
        if not tab or not self.find_dialog:
            return
        found = tab.find_next(
            self.find_dialog.find_entry.get_text(),
            self.find_dialog.case_check.get_active(),
        )
        if not found:
            self._error_dialog("Text not found.")

    def _on_replace(self, *_args) -> None:
        tab = self._current_tab()
        if not tab or not self.find_dialog:
            return
        if tab.buffer.get_has_selection():
            tab.replace_selection(self.find_dialog.replace_entry.get_text())
        self._on_find_next()

    def _undo(self) -> None:
        tab = self._current_tab()
        if tab and tab.buffer.can_undo():
            tab.buffer.undo()

    def _redo(self) -> None:
        tab = self._current_tab()
        if tab and tab.buffer.can_redo():
            tab.buffer.redo()

    def _duplicate_line(self) -> None:
        tab = self._current_tab()
        if not tab:
            return
        insert_iter = tab.buffer.get_iter_at_mark(tab.buffer.get_insert())
        line_start = insert_iter.copy()
        line_end = insert_iter.copy()
        line_start.set_line_offset(0)
        if not line_end.ends_line():
            line_end.forward_to_line_end()
        line_end.forward_char()
        text = tab.buffer.get_text(line_start, line_end, True)
        tab.buffer.insert(line_end, text)

    def _toggle_wrap(self, menu_item: Gtk.CheckMenuItem) -> None:
        mode = Gtk.WrapMode.WORD_CHAR if menu_item.get_active() else Gtk.WrapMode.NONE
        for tab in self._iter_tabs():
            tab.view.set_wrap_mode(mode)

    def _toggle_dark_theme(self, menu_item: Gtk.CheckMenuItem) -> None:
        dark = menu_item.get_active()
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", dark)
        _apply_editor_theme_css(dark)
        # Update the style scheme in every open tab to match the new theme.
        # notebook may not exist yet when called from _build_menu_bar (during __init__).
        nb = getattr(self, "notebook", None)
        if nb is not None:
            for tab in self._iter_tabs():
                tab._apply_style_scheme()

    def _sync_encoding_menu_from_current_tab(self) -> None:
        tab = self._current_tab()
        if not tab:
            return
        current = tab.encoding
        item = self.encoding_menu_items.get(current)
        if not item:
            return
        if item.get_active():
            return
        handler_id = self.encoding_menu_handlers.get(current)
        try:
            self._updating_encoding_menu = True
            if handler_id:
                item.handler_block(handler_id)
            item.set_active(True)
        finally:
            if handler_id:
                item.handler_unblock(handler_id)
            self._updating_encoding_menu = False

    def _on_encoding_selected(self, menu_item: Gtk.RadioMenuItem, encoding: str) -> None:
        if self._updating_encoding_menu or not menu_item.get_active():
            return
        tab = self._current_tab()
        if not tab:
            return
        try:
            if tab.path and not tab.modified:
                tab.reload_with_encoding(encoding)
            else:
                tab.set_encoding(encoding)
        except Exception as exc:
            self._error_dialog(f"Cannot reopen file with {encoding.upper()}:\n{exc}")
            self._sync_encoding_menu_from_current_tab()
            return
        self._refresh_tab_titles()
        self._update_status()

    def _on_language_selected(self, menu_item: Gtk.RadioMenuItem, language_id: str) -> None:
        if self._updating_language_menu or not menu_item.get_active():
            return
        tab = self._current_tab()
        if not tab:
            return
        tab.set_language(language_id)
        self._refresh_tab_titles()
        self._update_status()

    def _sync_language_menu_from_current_tab(self) -> None:
        tab = self._current_tab()
        if not tab:
            return
        current = tab._language_id
        item = self.language_menu_items.get(current)
        if not item:
            return
        if item.get_active():
            return
        handler_id = self.language_menu_handlers.get(current)
        try:
            self._updating_language_menu = True
            if handler_id:
                item.handler_block(handler_id)
            item.set_active(True)
        finally:
            if handler_id:
                item.handler_unblock(handler_id)
            self._updating_language_menu = False

    def _on_switch_page(self, *_args) -> None:
        self._schedule_current_tab_ui_sync()

    def _schedule_current_tab_ui_sync(self) -> None:
        if self._ui_sync_source_id:
            GLib.source_remove(self._ui_sync_source_id)
        self._ui_sync_source_id = GLib.idle_add(
            self._sync_current_tab_ui,
            priority=GLib.PRIORITY_DEFAULT_IDLE,
        )

    def _sync_current_tab_ui(self) -> bool:
        self._ui_sync_source_id = 0
        self._sync_encoding_menu_from_current_tab()
        self._sync_language_menu_from_current_tab()
        self._update_status()
        return False

    def _refresh_tab_titles(self) -> None:
        for tab in self._iter_tabs():
            header = self.notebook.get_tab_label(tab)
            if isinstance(header, Gtk.Box):
                label = self._tab_header_label(header)
                if label:
                    label.set_text(tab.get_title())
        self._update_status()

    def _tab_header_label(self, header: Gtk.Box) -> Optional[Gtk.Label]:
        for child in header.get_children():
            if isinstance(child, Gtk.Label):
                return child
            if isinstance(child, Gtk.Bin):
                nested = child.get_child()
                if isinstance(nested, Gtk.Label):
                    return nested
        return None

    def _update_status(self) -> None:
        self.status.pop(self.status_ctx)
        tab = self._current_tab()
        if not tab:
            return
        line, col = tab.cursor_position()
        name = str(tab.path) if tab.path else "Untitled"
        lang_label = LANG_LABELS.get(tab._language_id, tab._language_id)
        self.status.push(
            self.status_ctx,
            f"{name} | {tab.encoding.upper()} | {lang_label} | Ln {line}, Col {col}",
        )

    def _error_dialog(self, message: str) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message,
        )
        dialog.run()
        dialog.destroy()

    def _save_session(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tabs = []
        for tab in self._iter_tabs():
            item = {"path": str(tab.path) if tab.path else None, "encoding": tab.encoding}
            if tab.path is None:
                start, end = tab.buffer.get_bounds()
                item["content"] = tab.buffer.get_text(start, end, True)
            tabs.append(item)
        payload = {"tabs": tabs, "active": self.notebook.get_current_page()}
        self._write_json_atomic(SESSION_FILE, payload)
        self._save_settings()

    def _write_json_atomic(self, path: Path, payload: dict) -> None:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload), encoding="utf-8")
        tmp_path.replace(path)

    def _load_session(self) -> bool:
        if not SESSION_FILE.exists():
            return False
        try:
            payload = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
            session_tabs = payload.get("tabs", [])
            if not isinstance(session_tabs, list):
                return False
        except Exception as exc:
            sys.stderr.write(f"Cannot load session: {exc}\n")
            return False

        while self.notebook.get_n_pages() > 0:
            self.notebook.remove_page(0)

        for item in session_tabs:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            encoding = item.get("encoding", "utf-8")
            tab: EditorTab
            if path and Path(path).exists():
                try:
                    content = Path(path).read_text(encoding=encoding)
                except UnicodeDecodeError:
                    content, encoding = self._read_file_with_detected_encoding(Path(path))
                tab = EditorTab(path=Path(path), content=content, encoding=encoding)
            else:
                tab = EditorTab(
                    path=None, content=item.get("content", ""), encoding=encoding
                )

            self._add_tab(tab)

        if self.notebook.get_n_pages() == 0:
            return False
        active = payload.get("active", 0)
        self.notebook.set_current_page(max(0, min(active, self.notebook.get_n_pages() - 1)))
        self._sync_encoding_menu_from_current_tab()
        self._refresh_tab_titles()
        # Ensure style scheme is applied to all tabs after loading
        if hasattr(self, "_dark_item"):
            for tab in self._iter_tabs():
                tab._apply_style_scheme()
        return True

    def _on_quit(self) -> None:
        if not self._confirm_unsaved_before_quit():
            return
        self._save_session()
        self.get_application().quit()

    def _confirm_unsaved_before_quit(self) -> bool:
        unsaved = []
        for tab in self._iter_tabs():
            if tab.modified:
                unsaved.append(tab.get_title())
        if not unsaved:
            return True

        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            text="There are unsaved files.",
        )
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL, "Quit anyway", Gtk.ResponseType.YES
        )
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.YES

    def do_delete_event(self, _event: Gdk.Event) -> bool:
        self._on_quit()
        return True


class NotepadLinuxApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )

    def do_activate(self) -> None:
        window = self.props.active_window
        if not window:
            window = NotepadLinuxWindow(self)
        window.present()

    def do_open(self, files: list[Gio.File], _n_files: int, _hint: str) -> None:
        window = self.props.active_window
        if not window:
            window = NotepadLinuxWindow(self)

        paths = []
        unsupported = []
        for file in files:
            path = file.get_path()
            if path:
                paths.append(Path(path))
            else:
                unsupported.append(file.get_uri())

        if isinstance(window, NotepadLinuxWindow):
            window.open_files(paths)
            if unsupported:
                window._error_dialog(
                    "Only local files are supported:\n" + "\n".join(unsupported)
                )
        else:
            window.present()


def main() -> None:
    _install_warning_filters()
    if ICON_PATH.exists():
        Gtk.Window.set_default_icon_from_file(str(ICON_PATH))
    app = NotepadLinuxApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
