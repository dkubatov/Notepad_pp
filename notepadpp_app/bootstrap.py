from __future__ import annotations

import os
import sys


SNAP_ENV_VARS = [
    "CHROME_DESKTOP",
    "GDK_PIXBUF_MODULEDIR",
    "GDK_PIXBUF_MODULE_FILE",
    "GIO_LAUNCHED_DESKTOP_FILE",
    "GIO_LAUNCHED_DESKTOP_FILE_PID",
    "GIO_MODULE_DIR",
    "GSETTINGS_SCHEMA_DIR",
    "GTK_EXE_PREFIX",
    "GTK_IM_MODULE_FILE",
    "GTK_MODULES",
    "GTK_PATH",
    "LD_LIBRARY_PATH",
    "LOCPATH",
    "SNAP",
    "SNAP_ARCH",
    "SNAP_COMMON",
    "SNAP_CONTEXT",
    "SNAP_COOKIE",
    "SNAP_DATA",
    "SNAP_EUID",
    "SNAP_INSTANCE_NAME",
    "SNAP_LAUNCHER_ARCH_TRIPLET",
    "SNAP_LIBRARY_PATH",
    "SNAP_NAME",
    "SNAP_REAL_HOME",
    "SNAP_REVISION",
    "SNAP_UID",
    "SNAP_USER_COMMON",
    "SNAP_USER_DATA",
    "SNAP_VERSION",
    "XDG_DATA_HOME",
]


def reexec_without_snap_environment() -> None:
    if os.environ.get("NOTEPADPP_LINUX_CLEAN_ENV") == "1":
        return
    if not os.environ.get("SNAP") and not os.environ.get("GTK_PATH"):
        return

    clean_env = os.environ.copy()
    xdg_config_dirs = clean_env.get("XDG_CONFIG_DIRS_VSCODE_SNAP_ORIG")
    xdg_data_dirs = clean_env.get("XDG_DATA_DIRS_VSCODE_SNAP_ORIG")
    for name in SNAP_ENV_VARS:
        clean_env.pop(name, None)
    for name, value in list(clean_env.items()):
        if "/snap/" in value or "/var/lib/snapd/" in value or "/snapd/" in value:
            clean_env.pop(name, None)
    clean_env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    if xdg_config_dirs:
        clean_env["XDG_CONFIG_DIRS"] = xdg_config_dirs
    else:
        clean_env.pop("XDG_CONFIG_DIRS", None)
    if xdg_data_dirs:
        clean_env["XDG_DATA_DIRS"] = xdg_data_dirs
    else:
        clean_env.pop("XDG_DATA_DIRS", None)
    clean_env["NOTEPADPP_LINUX_CLEAN_ENV"] = "1"
    os.execvpe(sys.executable, [sys.executable, *sys.argv], clean_env)
