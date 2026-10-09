from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from desktop_pet.config import PROJECT_ROOT, load_spritesheet_config
from desktop_pet.desktop_pet import DesktopPet
from desktop_pet.hook_listener import HookListener


def main() -> None:
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Akita.DesktopPet")

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(PROJECT_ROOT / "icon.png")))
    app.setQuitOnLastWindowClosed(False)
    pet = DesktopPet(load_spritesheet_config())
    listener = HookListener(pet)
    listener.event_received.connect(pet.handle_event)
    app.aboutToQuit.connect(listener.close)
    pet.show()
    sys.exit(app.exec())
