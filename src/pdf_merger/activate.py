"""창을 맨 앞으로 가져와 포커스를 준다."""

import sys

from PySide6.QtWidgets import QWidget


def bring_to_front(window: QWidget) -> None:
    if window.isMinimized():
        window.showNormal()
    window.raise_()
    window.activateWindow()
    if sys.platform == "win32":
        _force_foreground(int(window.winId()))


def _force_foreground(hwnd: int) -> None:
    """Windows는 다른 프로그램이 앞에 있으면 창을 앞으로 가져오지 못하게 막고 작업 표시줄만 깜빡인다.
    지금 앞에 있는 창의 입력 스레드에 잠깐 붙어서 가져온다 (Qt의 AlwaysActivateWindow와 같은 방법)."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32")
    kernel32 = ctypes.WinDLL("kernel32")
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.BringWindowToTop.argtypes = [wintypes.HWND]

    foreground = user32.GetForegroundWindow()
    if foreground == hwnd:
        return
    my_thread = kernel32.GetCurrentThreadId()
    their_thread = user32.GetWindowThreadProcessId(foreground, None) if foreground else my_thread
    attached = their_thread != my_thread and user32.AttachThreadInput(my_thread, their_thread, True)
    try:
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(my_thread, their_thread, False)
