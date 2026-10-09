import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from notepadpp_app import file_io
from notepadpp_app.file_io import read_text, write_text_atomically


class FileIOTests(unittest.TestCase):
    def test_read_text_normalizes_all_newline_styles(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lines.txt"
            path.write_bytes(b"one\r\ntwo\rthree\n")

            self.assertEqual(read_text(path, "utf-8"), "one\ntwo\nthree\n")

    def test_atomic_write_preserves_existing_mode_and_xattrs(self):
        if not hasattr(os, "setxattr"):
            self.skipTest("extended attributes are unavailable")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "document.txt"
            path.write_text("before", encoding="utf-8")
            path.chmod(0o640)
            try:
                os.setxattr(path, "user.notepadpp-test", b"keep")
            except OSError as exc:
                self.skipTest(f"extended attributes are unavailable: {exc}")

            write_text_atomically(path, "after", "utf-8")

            self.assertEqual(path.read_text(encoding="utf-8"), "after")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
            self.assertEqual(os.getxattr(path, "user.notepadpp-test"), b"keep")

    def test_existing_file_saves_if_sibling_temp_cannot_be_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "document.txt"
            path.write_text("before", encoding="utf-8")

            with patch.object(
                file_io.tempfile,
                "mkstemp",
                side_effect=PermissionError("directory is not writable"),
            ):
                write_text_atomically(path, "after", "utf-8")

            self.assertEqual(path.read_text(encoding="utf-8"), "after")

    def test_encoding_error_keeps_original_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "document.txt"
            path.write_text("original", encoding="utf-8")
            original = path.read_bytes()

            with self.assertRaises(UnicodeEncodeError):
                write_text_atomically(path, "Кириллица", "ascii")

            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
