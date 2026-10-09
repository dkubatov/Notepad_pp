#!/usr/bin/env python3
"""Entry point for Notepad Light."""

from __future__ import annotations

from notepadpp_app.bootstrap import reexec_without_snap_environment


def main() -> None:
    reexec_without_snap_environment()
    from notepadpp_app.app import main as run_app

    run_app()


if __name__ == "__main__":
    main()
