"""Manage the shared pet-hook command in the Windows user PATH."""

from __future__ import annotations

import ctypes
import ntpath
import os
from pathlib import Path
import sys
import winreg


CLI_DIRECTORY = Path(__file__).resolve().parents[2] / "bin"
CLI_COMMAND = CLI_DIRECTORY / "pet-hook.cmd"
CLI_SCRIPT = CLI_DIRECTORY / "pet_hook.py"


def _same_directory(entry: str, target: Path) -> bool:
    expanded = os.path.expandvars(entry.strip().strip('"'))
    return ntpath.normcase(ntpath.normpath(expanded)) == ntpath.normcase(
        ntpath.normpath(str(target))
    )


def _contains_directory(path_value: str, target: Path) -> bool:
    return any(
        _same_directory(entry, target)
        for entry in path_value.split(";")
        if entry.strip()
    )


def _require_windows() -> None:
    if sys.platform != "win32":
        raise OSError("加入 PATH 僅支援 Windows。")


def is_cli_in_user_path(directory: Path = CLI_DIRECTORY) -> bool:
    _require_windows()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, "Path")
    except FileNotFoundError:
        return False
    return isinstance(value, str) and _contains_directory(value, directory)


def _notify_environment_changed() -> None:
    notify = ctypes.windll.user32.SendMessageTimeoutW
    notify.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_size_t,
        ctypes.c_ssize_t,
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.POINTER(ctypes.c_size_t),
    )
    notify.restype = ctypes.c_ssize_t
    environment = ctypes.create_unicode_buffer("Environment")
    result = ctypes.c_size_t()
    notify(
        0xFFFF, 0x001A, 0,
        ctypes.cast(environment, ctypes.c_void_p).value,
        0x0002, 1000, ctypes.byref(result),
    )


def add_cli_to_user_path(directory: Path = CLI_DIRECTORY) -> bool:
    """Append the CLI directory once; preserve the user's other PATH entries."""
    _require_windows()
    if not (directory / CLI_COMMAND.name).is_file() or not (
        directory / CLI_SCRIPT.name
    ).is_file():
        raise FileNotFoundError("找不到共用 CLI 腳本，無法加入 PATH。")

    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        "Environment",
        0,
        winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE,
    ) as key:
        try:
            value, value_type = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            value, value_type = "", winreg.REG_EXPAND_SZ
        if not isinstance(value, str) or value_type not in (
            winreg.REG_SZ, winreg.REG_EXPAND_SZ
        ):
            raise ValueError("使用者 PATH 不是文字設定，無法安全更新。")
        if _contains_directory(value, directory):
            return False
        separator = ";" if value and not value.endswith(";") else ""
        winreg.SetValueEx(
            key, "Path", 0, value_type, value + separator + str(directory)
        )

    current_path = os.environ.get("PATH", "")
    if not _contains_directory(current_path, directory):
        separator = ";" if current_path and not current_path.endswith(";") else ""
        os.environ["PATH"] = current_path + separator + str(directory)
    try:
        _notify_environment_changed()
    except (OSError, AttributeError):
        pass  # The registry value is saved; newly started apps can still read it.
    return True
