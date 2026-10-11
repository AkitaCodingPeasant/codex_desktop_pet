from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from desktop_pet.config import PROJECT_ROOT, load_spritesheet_config
from desktop_pet.desktop_pet import DesktopPet
from desktop_pet.hook_listener import HookListener
from desktop_pet.startup_animation import StartupAnimation


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
    intro = StartupAnimation(PROJECT_ROOT / "assets" / "intro.yaml")
    intro.finished.connect(pet.show)

    def replay_intro() -> None:
        pet.hide()
        intro.start()

    pet.intro_replay_requested.connect(replay_intro)
    intro.start()
    sys.exit(app.exec())
