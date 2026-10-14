from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QPoint, QSettings, QTimer, Signal, Qt
from PySide6.QtWidgets import QApplication

from desktop_pet import app as pet_app
from desktop_pet.config import PROJECT_ROOT, load_spritesheet_config
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
    def test_legacy_left_edge_offset_is_migrated_to_center_offset(self) -> None:
        qt_app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as temporary:
            settings = QSettings(
                str(Path(temporary) / "pet.ini"), QSettings.Format.IniFormat
            )
            settings.setValue("session_panel_offset_x", 0)
            settings.setValue("session_panel_offset_y", 15)
            with (
                patch("desktop_pet.desktop_pet.QSettings", return_value=settings),
                patch("desktop_pet.desktop_pet.keep_topmost"),
            ):
                pet = DesktopPet(load_spritesheet_config())
                try:
                    pet.show()
                    qt_app.processEvents()
                    area = qt_app.primaryScreen().availableGeometry()
                    pet.move(area.center().x() - pet.width() // 2, area.top() + 50)
                    pet._position_session_panel()
                    self.assertEqual(pet.session_panel.x(), pet.x())
                    self.assertEqual(pet.session_panel.y(), pet.y() + 15)
                    self.assertEqual(
                        pet.session_offset.x(),
                        pet.session_panel.width() // 2 - pet.width() // 2,
                    )
                    self.assertTrue(settings.value("session_panel_offset_centered", type=bool))
                finally:
                    pet.close()

    def test_context_menu_swaps_default_panel_side_and_persists(self) -> None:
        qt_app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as temporary:
            settings = QSettings(
                str(Path(temporary) / "pet.ini"), QSettings.Format.IniFormat
            )

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
                    return self.actions["工作狀態面板位置對調"]

            with (
                patch("desktop_pet.desktop_pet.QSettings", return_value=settings),
                patch("desktop_pet.desktop_pet.QMenu", FakeMenu),
                patch("desktop_pet.desktop_pet.keep_topmost"),
            ):
                pet = DesktopPet(load_spritesheet_config())
                try:
                    pet.show()
                    qt_app.processEvents()
                    area = qt_app.primaryScreen().availableGeometry()
                    pet.move(area.center().x() - pet.width() // 2, area.top() + 50)
                    pet._position_session_panel()
                    self.assertGreater(pet.session_panel.x(), pet.x())
                    initial_x = pet._session_horizontal_offset()

                    pet.contextMenuEvent(MenuEvent())
                    self.assertTrue(pet.session_panel_left)
                    self.assertEqual(pet.session_offset.x(), -initial_x)
                    self.assertLess(pet.session_panel.x(), pet.x())
                    self.assertTrue(settings.value("session_panel_left", type=bool))

                    pet.move(area.left(), area.top() + 50)
                    pet._position_session_panel()
                    self.assertGreater(pet.session_panel.x(), pet.x())

                    pet.contextMenuEvent(MenuEvent())
                    self.assertFalse(pet.session_panel_left)
                    self.assertEqual(pet.session_offset.x(), initial_x)
                    self.assertFalse(settings.value("session_panel_left", type=bool))
                    pet.contextMenuEvent(MenuEvent())
                finally:
                    pet.close()

                restored = DesktopPet(load_spritesheet_config())
                try:
                    restored.show()
                    qt_app.processEvents()
                    restored.move(area.center().x() - restored.width() // 2, area.top() + 50)
                    restored._position_session_panel()
                    self.assertTrue(restored.session_panel_left)
                    self.assertLess(restored.session_panel.x(), restored.x())

                    restored.open_settings()
                    restored.settings_panel.session_x_spin.setValue(100)
                    self.assertEqual(restored.session_offset.x(), 100)
                    restored.contextMenuEvent(MenuEvent())
                    self.assertEqual(restored.session_offset.x(), -100)
                    self.assertEqual(settings.value("session_panel_offset_x", type=int), -100)
                    self.assertEqual(restored.settings_panel.session_x_spin.value(), -100)
                    self.assertEqual(
                        restored.session_panel.x() + restored.session_panel.width() // 2
                        - restored.x() - restored.width() // 2,
                        -100,
                    )
                finally:
                    restored.close()

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
                    separation = pet.width() // 2 + pet.session_panel.width() // 2 + gap
                    pet.set_session_offset(-separation, 0)
                    self.assertEqual(
                        pet.session_panel.x(),
                        min(area.right() - pet.session_panel.width() + 1,
                            pet.x() + pet.width() + gap),
                    )

                    pet.move(area.right() - pet.width() + 1, y)
                    pet.set_session_offset(separation, 0)
                    self.assertEqual(
                        pet.session_panel.x(),
                        max(area.left(), pet.x() - pet.session_panel.width() - gap),
                    )

                    pet.move(area.left() + (area.width() - pet.width()) // 2, y)
                    pet._position_session_panel()
                    self.assertEqual(
                        pet.session_panel.x(),
                        min(area.right() - pet.session_panel.width() + 1,
                            pet.x() + pet.width() + gap),
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
                    area = qt_app.primaryScreen().availableGeometry()
                    pet.move(area.center().x() - pet.width() // 2, area.top() + 50)
                    pet._position_session_panel()
                    pet.open_settings()
                    panel = pet.settings_panel
                    self.assertEqual(
                        panel.session_x_spin.value(), pet._session_horizontal_offset(),
                    )
                    self.assertEqual(
                        panel.session_y_spin.value(), pet.session_panel.y() - pet.y()
                    )

                    panel.session_x_spin.setValue(20)
                    panel.session_y_spin.setValue(30)
                    self.assertEqual(
                        pet.session_panel.x() + pet.session_panel.width() // 2
                        - pet.x() - pet.width() // 2,
                        20,
                    )
                    self.assertEqual(pet.session_panel.y(), pet.y() + 30)
                    pet.move(80, 80)
                    pet._position_session_panel()
                    self.assertEqual(
                        pet.session_panel.x(),
                        pet.x() + pet.width() // 2 + 20 - pet.session_panel.width() // 2,
                    )
                    self.assertEqual(pet.session_panel.y(), 110)
                    self.assertEqual(settings.value("session_panel_offset_x", type=int), 20)
                    self.assertEqual(settings.value("session_panel_offset_y", type=int), 30)
                    self.assertTrue(settings.value("session_panel_offset_centered", type=bool))
                finally:
                    pet.close()

                restored = DesktopPet(load_spritesheet_config())
                try:
                    restored.show()
                    qt_app.processEvents()
                    restored.move(area.center().x() - restored.width() // 2, area.top() + 50)
                    restored._position_session_panel()
                    self.assertEqual(restored.session_offset, QPoint(20, 30))
                    self.assertEqual(
                        restored.session_panel.x() + restored.session_panel.width() // 2
                        - restored.x() - restored.width() // 2,
                        20,
                    )
                finally:
                    restored.close()

    def test_session_panel_opacity_applies_and_persists(self) -> None:
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
                    pet.open_settings()
                    panel = pet.settings_panel
                    self.assertEqual(panel.session_opacity_spin.value(), 100)

                    panel.session_opacity_slider.setValue(65)
                    self.assertEqual(pet.session_opacity, 65)
                    self.assertAlmostEqual(
                        pet.session_panel.windowOpacity(), 0.65, delta=0.01
                    )
                    self.assertEqual(
                        settings.value("session_panel_opacity", type=int), 65
                    )
                finally:
                    pet.close()

                restored = DesktopPet(load_spritesheet_config())
                try:
                    self.assertEqual(restored.session_opacity, 65)
                    self.assertAlmostEqual(
                        restored.session_panel.windowOpacity(), 0.65, delta=0.01
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

    def test_context_menu_opens_project_repo_in_vscode(self) -> None:
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
                return self.actions["打開專案 repo"]

        try:
            with (
                patch("desktop_pet.desktop_pet.QMenu", FakeMenu),
                patch("desktop_pet.desktop_pet.shutil.which", return_value="code.cmd"),
                patch("desktop_pet.desktop_pet.subprocess.Popen") as launch,
            ):
                pet.contextMenuEvent(MenuEvent())
            launch.assert_called_once_with(
                ["code.cmd", str(PROJECT_ROOT)],
                cwd=PROJECT_ROOT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
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
