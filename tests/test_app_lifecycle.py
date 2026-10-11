from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QPoint, QTimer, Signal
from PySide6.QtWidgets import QApplication

from desktop_pet import app as pet_app
from desktop_pet.config import load_spritesheet_config
from desktop_pet.desktop_pet import DesktopPet


class FakeStartupAnimation(QObject):
    finished = Signal()

    def __init__(self, config_path):
        super().__init__()
        self.start_count = 0
        FakeStartupAnimation.latest = self

    def start(self) -> None:
        self.start_count += 1
        QTimer.singleShot(0, self.finished.emit)


class AppLifecycleTests(unittest.TestCase):
    def test_closing_settings_keeps_desktop_pet_running(self) -> None:
        qt_app = QApplication.instance() or QApplication([])
        original_quit_setting = qt_app.quitOnLastWindowClosed()
        observed: dict[str, bool] = {}

        def close_settings() -> None:
            pet = next(widget for widget in qt_app.topLevelWidgets() if isinstance(widget, DesktopPet))
            observed["pet_hidden_during_intro"] = not pet.isVisible()
            pet.open_settings()
            panel = pet.settings_panel
            panel.close()

            def verify_and_quit() -> None:
                observed["pet_visible"] = pet.isVisible()
                observed["panel_hidden"] = not panel.isVisible()
                pet.intro_replay_requested.emit()
                observed["pet_hidden_during_replay"] = not pet.isVisible()

                def verify_replay_finished() -> None:
                    observed["pet_visible_after_replay"] = pet.isVisible()
                    observed["intro_start_count"] = FakeStartupAnimation.latest.start_count
                    pet.close()
                    qt_app.quit()

                QTimer.singleShot(20, verify_replay_finished)

            QTimer.singleShot(50, verify_and_quit)

        try:
            QTimer.singleShot(0, close_settings)
            with (
                patch.object(pet_app, "QApplication", return_value=qt_app),
                patch.object(pet_app, "HookListener"),
                patch.object(pet_app, "StartupAnimation", FakeStartupAnimation),
                patch.object(pet_app.sys, "exit"),
                patch("desktop_pet.desktop_pet.keep_topmost"),
            ):
                pet_app.main()
            self.assertEqual(observed, {
                "pet_hidden_during_intro": True,
                "pet_visible": True,
                "panel_hidden": True,
                "pet_hidden_during_replay": True,
                "pet_visible_after_replay": True,
                "intro_start_count": 2,
            })
        finally:
            qt_app.setQuitOnLastWindowClosed(original_quit_setting)
            for widget in qt_app.topLevelWidgets():
                widget.close()

    def test_context_menu_requests_intro_replay(self) -> None:
        app = QApplication.instance() or QApplication([])
        pet = DesktopPet(load_spritesheet_config())
        requested = []
        pet.intro_replay_requested.connect(lambda: requested.append(True))

        class MenuEvent:
            def globalPos(self):
                return QPoint(0, 0)

        class FakeMenu:
            def __init__(self, parent):
                self.actions = []

            def addAction(self, label):
                action = object()
                self.actions.append(action)
                return action

            def exec(self, position):
                return self.actions[0]

        try:
            with patch("desktop_pet.desktop_pet.QMenu", FakeMenu):
                pet.contextMenuEvent(MenuEvent())
            self.assertEqual(requested, [True])
        finally:
            pet.close()

    def test_hiding_pet_for_intro_hides_reply_bubble(self) -> None:
        app = QApplication.instance() or QApplication([])
        with patch("desktop_pet.desktop_pet.keep_topmost"):
            pet = DesktopPet(load_spritesheet_config())
            try:
                pet.show()
                pet._show_reply("Hello")
                self.assertTrue(pet.reply_bubble.isVisible())
                pet.hide()
                self.assertFalse(pet.reply_bubble.isVisible())
            finally:
                pet.close()


if __name__ == "__main__":
    unittest.main()
