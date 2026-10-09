from __future__ import annotations

import os
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtGui import QPixmap

import desktop_pet.hook_bridge as bridge
import desktop_pet.hook_listener as listener_module
from desktop_pet.config import load_spritesheet_config
from desktop_pet.desktop_pet import DesktopPet
from desktop_pet.hook_listener import HookListener
from desktop_pet.settings_panel import SettingsPanel


class HookPanelTests(unittest.TestCase):
    def test_hook_settings_button_installs_and_reports_result(self) -> None:
        app = QApplication.instance() or QApplication([])
        with patch("desktop_pet.settings_panel.install_hooks", return_value=(
            Path("D:/codex/hooks.json"), True,
        )) as install:
            panel = SettingsPanel(100, 8, QPixmap(16, 16))
            try:
                panel.hook_settings_button.click()
                self.assertEqual(panel.pages.currentIndex(), 2)
                panel.install_hook_button.click()
                install.assert_called_once_with()
                self.assertIn("Hook 已設定／更新", panel.hook_install_result.text())
                self.assertIn("/hooks", panel.hook_install_result.text())
            finally:
                panel.close()
        self.assertIsNotNone(app)

    def test_change_summary_button_shows_below_reply(self) -> None:
        app = QApplication.instance() or QApplication([])
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as temporary:
            temporary.bind((bridge.HOST, 0))
            port = temporary.getsockname()[1]
        with (
            patch.object(bridge, "PORT", port),
            patch.object(listener_module, "PORT", port),
            patch("desktop_pet.desktop_pet.keep_topmost"),
        ):
            pet = DesktopPet(load_spritesheet_config())
            listener = HookListener()
            listener.event_received.connect(pet.handle_event)
            try:
                pet.show()
                pet.open_settings()
                pet.settings_panel.hook_button.click()
                pet.settings_panel.change_test_button.click()
                listener._receive_pending()
                app.processEvents()
                bubble = pet.reply_bubble
                self.assertEqual(bubble.text(), "測試回覆")
                self.assertEqual(bubble.change_summary_label.text(), "已變更 1 個檔案")
                self.assertEqual(bubble.added_lines_label.text(), "+1")
                self.assertEqual(bubble.removed_lines_label.text(), "-1")
                self.assertTrue(bubble.change_summary.isVisible())
                self.assertGreater(
                    bubble.change_summary.y(),
                    bubble.message_label.y(),
                )
                self.assertIn("#6b7785", bubble.styleSheet())
                self.assertIn("#168a54", bubble.styleSheet())
                self.assertIn("#c94b58", bubble.styleSheet())
                bubble.setText("普通回覆")
                self.assertEqual(bubble.text(), "普通回覆")
                self.assertFalse(bubble.change_summary.isVisible())
            finally:
                listener.close()
                pet.close()

    def test_navigation_and_hook_buttons_reach_pet_through_listener(self) -> None:
        app = QApplication.instance() or QApplication([])
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as temporary:
            temporary.bind((bridge.HOST, 0))
            port = temporary.getsockname()[1]

        with (
            patch.object(bridge, "PORT", port),
            patch.object(listener_module, "PORT", port),
            patch("desktop_pet.desktop_pet.keep_topmost"),
        ):
            pet = DesktopPet(load_spritesheet_config())
            listener = HookListener()
            listener.event_received.connect(pet.handle_event)
            try:
                pet.show()
                pet.open_settings()
                panel = pet.settings_panel
                self.assertEqual(panel.pages.currentIndex(), 0)
                self.assertTrue(panel.settings_button.isChecked())
                panel.hook_button.click()
                self.assertEqual(panel.pages.currentIndex(), 1)
                self.assertTrue(panel.hook_button.isChecked())
                event_buttons = {
                    button.text().split("  ·")[0]: button
                    for button in panel.pages.widget(1).findChildren(QPushButton)
                    if button.objectName() == "eventButton"
                }

                event_buttons["送出提示"].click()
                listener._receive_pending()
                self.assertEqual(pet.status_text, "工作中")
                self.assertEqual(panel.active_count_value.text(), "1")

                event_buttons["工具開始"].click()
                listener._receive_pending()
                self.assertEqual(pet.state, "working")
                self.assertEqual(pet.animation_name, "working_intro")
                self.assertEqual(panel.status_value.text(), "操作工具中")

                event_buttons["工具執行後"].click()
                listener._receive_pending()
                self.assertEqual(pet.state, "thinking")

                event_buttons["請求授權"].click()
                listener._receive_pending()
                self.assertEqual(pet.status_text, "等待授權")

                bridge.send_event("user_input_requested", session_id=panel._test_session_id, turn_id=panel._test_turn_id)
                listener._receive_pending()
                self.assertEqual(pet.state, "asking")
                self.assertEqual(pet.status_text, "等待回覆")

                panel.test_message.setText("測試回覆")
                event_buttons["回合完成"].click()
                listener._receive_pending()
                self.assertEqual(pet.status_text, "剛完成")
                self.assertEqual(pet.reply_bubble.text(), "測試回覆")
                self.assertEqual(panel.active_count_value.text(), "0")

                panel.settings_button.click()
                self.assertEqual(panel.pages.currentIndex(), 0)
                self.assertEqual(panel.scale_spin.value(), pet.scale_percent)
            finally:
                listener.close()
                pet.close()
        self.assertIsNotNone(app)
