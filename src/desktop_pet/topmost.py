from __future__ import annotations

import sys


def keep_topmost(window_id: int) -> bool:
    """Move a Windows window above other topmost windows without activating it."""
    if sys.platform != "win32":
        return False

    import ctypes
    from ctypes import wintypes

    set_window_pos = ctypes.windll.user32.SetWindowPos
    set_window_pos.argtypes = (
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    )
    set_window_pos.restype = wintypes.BOOL

    hwnd_topmost = wintypes.HWND(-1)
    swp_nosize = 0x0001
    swp_nomove = 0x0002
    swp_noactivate = 0x0010
    swp_noownerzorder = 0x0200
    flags = swp_nosize | swp_nomove | swp_noactivate | swp_noownerzorder
    return bool(set_window_pos(window_id, hwnd_topmost, 0, 0, 0, 0, flags))
