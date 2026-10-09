from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from desktop_pet.config import load_spritesheet_config
from desktop_pet.desktop_pet import DesktopPet
from desktop_pet.hook_listener import HookListener


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    pet = DesktopPet(load_spritesheet_config())
    listener = HookListener(pet)
    listener.event_received.connect(pet.handle_event)
    app.aboutToQuit.connect(listener.close)
    pet.show()
    sys.exit(app.exec())
