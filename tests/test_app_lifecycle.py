from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QPoint, QSettings, QTimer, Signal, Qt
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
    def test_session_panel_offset_mirrors_at_both_screen_edges(self) -> None:
        qt_app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as temporary:
            settings = QSettings(
                str(Path(temporary) / "pet.ini"), QSettings.Format.IniFormat
            )
            with (
                patch("desktop_pet.desktop_pet.QSettings", return_value=settings),
                patch("desktop_pet.desktop_pet.keep_topmost"),
            ):
                pet = DesktopPet(load_spritesheet_config())
                try:
                    pet.show()
                    qt_app.processEvents()
                    area = qt_app.primaryScreen().availableGeometry()
                    gap = 8
                    y = area.top() + 50

                    pet.move(area.left(), y)
                    pet.set_session_offset(-pet.session_panel.width() - gap, 0)
                    self.assertEqual(
                        pet.session_panel.x(), pet.x() + pet.width() + gap
                    )

                    pet.move(area.right() - pet.width() + 1, y)
                    pet.set_session_offset(pet.width() + gap, 0)
                    self.assertEqual(
                        pet.session_panel.x(), pet.x() - pet.session_panel.width() - gap
                    )

                    pet.move(area.left() + (area.width() - pet.width()) // 2, y)
                    pet._position_session_panel()
                    self.assertEqual(
                        pet.session_panel.x(), pet.x() + pet.width() + gap
                    )
                finally:
                    pet.close()

    def test_session_panel_relative_offset_applies_and_persists(self) -> None:
        qt_app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as temporary:
            settings = QSettings(
                str(Path(temporary) / "pet.ini"), QSettings.Format.IniFormat
            )
            with (
                patch("desktop_pet.desktop_pet.QSettings", return_value=settings),
                patch("desktop_pet.desktop_pet.keep_topmost"),
            ):
                pet = DesktopPet(load_spritesheet_config())
                try:
                    pet.show()
                    qt_app.processEvents()
                    self.assertIsNone(pet.session_offset)
                    pet.open_settings()
                    panel = pet.settings_panel
                    self.assertEqual(
                        panel.session_x_spin.value(), pet.session_panel.x() - pet.x()
                    )
                    self.assertEqual(
                        panel.session_y_spin.value(), pet.session_panel.y() - pet.y()
                    )

                    panel.session_x_spin.setValue(20)
                    panel.session_y_spin.setValue(30)
                    self.assertEqual(pet.session_panel.pos(), pet.pos() + QPoint(20, 30))
                    pet.move(80, 80)
                    pet._position_session_panel()
                    self.assertEqual(pet.session_panel.pos(), QPoint(100, 110))
                    self.assertEqual(settings.value("session_panel_offset_x", type=int), 20)
                    self.assertEqual(settings.value("session_panel_offset_y", type=int), 30)
                finally:
                    pet.close()

                restored = DesktopPet(load_spritesheet_config())
                try:
                    restored.show()
                    qt_app.processEvents()
                    self.assertEqual(
                        restored.session_panel.pos(), restored.pos() + QPoint(20, 30)
                    )
                finally:
                    restored.close()

    def test_intro_setting_persists_and_disables_startup_playback(self) -> None:
        qt_app = QApplication.instance() or QApplication([])
        original_quit_setting = qt_app.quitOnLastWindowClosed()
        observed = {}
        created_pets = []
        with tempfile.TemporaryDirectory() as temporary:
            settings_path = Path(temporary) / "pet.ini"
            settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
            settings.setValue("play_intro", False)

            def create_pet(config):
                pet = DesktopPet(config)
                created_pets.append(pet)
                return pet

            def verify_startup() -> None:
                pet = created_pets[0]
                observed["visible_without_intro"] = pet.isVisible()
                observed["intro_start_count"] = FakeStartupAnimation.latest.start_count
                pet.open_settings()
                observed["checkbox_off"] = not pet.settings_panel.play_intro_checkbox.isChecked()
                pet.settings_panel.play_intro_checkbox.setChecked(True)
                observed["saved_enabled"] = settings.value("play_intro", type=bool)
                pet.settings_panel.close()
                pet.set_play_intro(False)
                pet.intro_replay_requested.emit()
                observed["hidden_for_manual_replay"] = not pet.isVisible()

                def verify_replay() -> None:
                    observed["visible_after_replay"] = pet.isVisible()
                    observed["manual_replay_count"] = FakeStartupAnimation.latest.start_count
                    pet.close()
                    qt_app.quit()

                QTimer.singleShot(20, verify_replay)

            try:
                QTimer.singleShot(0, verify_startup)
                QTimer.singleShot(1000, qt_app.quit)
                with (
                    patch.object(pet_app, "QApplication", return_value=qt_app),
                    patch.object(pet_app, "HookListener"),
                    patch.object(pet_app, "StartupAnimation", FakeStartupAnimation),
                    patch.object(pet_app, "DesktopPet", side_effect=create_pet),
                    patch.object(pet_app.sys, "exit"),
                    patch("desktop_pet.desktop_pet.QSettings", return_value=settings),
                    patch("desktop_pet.desktop_pet.keep_topmost"),
                ):
                    pet_app.main()
                self.assertEqual(observed, {
                    "visible_without_intro": True,
                    "intro_start_count": 0,
                    "checkbox_off": True,
                    "saved_enabled": True,
                    "hidden_for_manual_replay": True,
                    "visible_after_replay": True,
                    "manual_replay_count": 1,
                })
            finally:
                qt_app.setQuitOnLastWindowClosed(original_quit_setting)
                for widget in qt_app.topLevelWidgets():
                    widget.close()

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

            def setWindowFlag(self, flag):
                pass

            def addAction(self, label):
                action = object()
                self.actions.append((label, action))
                return action

            def exec(self, position):
                return next(action for label, action in self.actions if label == "重新播放開機動畫")

        try:
            with patch("desktop_pet.desktop_pet.QMenu", FakeMenu):
                pet.contextMenuEvent(MenuEvent())
            self.assertEqual(requested, [True])
        finally:
            pet.close()

    def test_context_menu_opens_settings(self) -> None:
        QApplication.instance() or QApplication([])
        pet = DesktopPet(load_spritesheet_config())

        class MenuEvent:
            def globalPos(self):
                return QPoint(0, 0)

        class FakeMenu:
            def __init__(self, parent):
                self.actions = {}

            def setWindowFlag(self, flag):
                pass

            def addAction(self, label):
                action = object()
                self.actions[label] = action
                return action

            def exec(self, position):
                return self.actions["設定"]

        try:
            with patch("desktop_pet.desktop_pet.QMenu", FakeMenu):
                pet.contextMenuEvent(MenuEvent())
            self.assertIsNotNone(pet.settings_panel)
            self.assertTrue(pet.settings_panel.isVisible())
        finally:
            pet.close()

    def test_context_menu_stays_above_pet_during_topmost_refresh(self) -> None:
        app = QApplication.instance() or QApplication([])
        pet = DesktopPet(load_spritesheet_config())
        pet.show()
        observed = {}

        class MenuEvent:
            def globalPos(self):
                return QPoint(0, 0)

        class FakeMenu:
            def __init__(self, parent):
                self.actions = []

            def setWindowFlag(self, flag):
                observed["topmost_flag"] = flag == Qt.WindowType.WindowStaysOnTopHint

            def addAction(self, label):
                action = object()
                self.actions.append(action)
                return action

            def isVisible(self):
                return True

            def winId(self):
                return 12345

            def exec(self, position):
                pet.keep_on_top()
                return None

        try:
            with (
                patch("desktop_pet.desktop_pet.QMenu", FakeMenu),
                patch("desktop_pet.desktop_pet.keep_topmost") as keep_topmost_mock,
            ):
                pet.contextMenuEvent(MenuEvent())
            self.assertTrue(observed["topmost_flag"])
            self.assertEqual(
                [call.args[0] for call in keep_topmost_mock.call_args_list],
                [int(pet.winId()), int(pet.session_panel.winId()), 12345],
            )
            self.assertIsNone(pet.context_menu)
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
