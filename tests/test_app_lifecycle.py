from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from desktop_pet import app as pet_app
from desktop_pet.desktop_pet import DesktopPet


class AppLifecycleTests(unittest.TestCase):
    def test_closing_settings_keeps_desktop_pet_running(self) -> None:
        qt_app = QApplication.instance() or QApplication([])
        original_quit_setting = qt_app.quitOnLastWindowClosed()
        observed: dict[str, bool] = {}

        def close_settings() -> None:
            pet = next(widget for widget in qt_app.topLevelWidgets() if isinstance(widget, DesktopPet))
            pet.open_settings()
            panel = pet.settings_panel
            panel.close()

            def verify_and_quit() -> None:
                observed["pet_visible"] = pet.isVisible()
                observed["panel_hidden"] = not panel.isVisible()
                pet.close()
                qt_app.quit()

            QTimer.singleShot(50, verify_and_quit)

        try:
            QTimer.singleShot(0, close_settings)
            with (
                patch.object(pet_app, "QApplication", return_value=qt_app),
                patch.object(pet_app, "HookListener"),
                patch.object(pet_app.sys, "exit"),
                patch("desktop_pet.desktop_pet.keep_topmost"),
            ):
                pet_app.main()
            self.assertEqual(observed, {"pet_visible": True, "panel_hidden": True})
        finally:
            qt_app.setQuitOnLastWindowClosed(original_quit_setting)
            for widget in qt_app.topLevelWidgets():
                widget.close()


if __name__ == "__main__":
    unittest.main()
