from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop_pet.config import load_spritesheet_config
from desktop_pet.desktop_pet import DesktopPet
from desktop_pet.session_panel import MAX_PANEL_WIDTH, MIN_PANEL_WIDTH, TurnPanel


class TurnPanelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = QApplication.instance() or QApplication([])
        self.topmost_patch = patch("desktop_pet.desktop_pet.keep_topmost")
        self.topmost_patch.start()
        self.pet = DesktopPet(load_spritesheet_config())
        self.pet.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.pet.close()
        self.topmost_patch.stop()

    def test_each_session_keeps_its_status_until_dismissed(self) -> None:
        first = ("session-a", "turn-a")
        second = ("session-b", "turn-b")
        self.pet.handle_event("turn.started", session_id=first[0], turn_id=first[1])
        self.pet.handle_event("turn.started", session_id=second[0], turn_id=second[1])
        panel = self.pet.session_panel
        self.assertEqual(len(panel.rows), 2)
        self.assertEqual(panel.rows[first[0]].status_label.text(), "思考中")
        self.assertEqual(panel.rows[first[0]].name_label.text(), "Session 1")
        self.assertEqual(panel.rows[second[0]].name_label.text(), "Session 2")
        self.assertEqual(panel.heading.text(), "SESSION 工作狀態")
        self.assertFalse(panel.rows[first[0]].dismiss_button.isEnabled())
        panel.dismiss_session(first[0])
        self.assertIn(first[0], panel.rows)

        self.pet.handle_event("tool.started", session_id=first[0], turn_id=first[1])
        self.assertEqual(panel.rows[first[0]].status_label.text(), "調用工具中")
        self.pet.handle_event("action_required", session_id=second[0], turn_id=second[1])
        self.assertEqual(panel.rows[second[0]].status_label.text(), "等待授權")
        self.pet.handle_event("turn.completed", session_id=first[0], turn_id=first[1])
        self.assertEqual(panel.rows[first[0]].status_label.text(), "已完成")
        self.assertTrue(panel.rows[first[0]].dismiss_button.isEnabled())
        self.assertFalse(panel.rows[second[0]].dismiss_button.isEnabled())
        panel.rows[first[0]].dismiss_button.click()
        self.assertNotIn(first[0], panel.rows)
        self.assertIn(second[0], panel.rows)

    def test_next_turn_reuses_session_number_after_dismissal(self) -> None:
        self.pet.handle_event("turn.started", session_id="session-a", turn_id="turn-1")
        self.pet.handle_event("turn.completed", session_id="session-a", turn_id="turn-1")
        panel = self.pet.session_panel
        panel.rows["session-a"].dismiss_button.click()
        self.assertNotIn("session-a", panel.rows)

        self.pet.handle_event("turn.started", session_id="session-a", turn_id="turn-2")
        self.assertEqual(len(panel.rows), 1)
        self.assertEqual(panel.rows["session-a"].name_label.text(), "Session 1")
        self.assertEqual(panel.rows["session-a"].status_label.text(), "思考中")
        self.assertFalse(panel.rows["session-a"].dismiss_button.isEnabled())

        self.pet.handle_event("turn.completed", session_id="session-a", turn_id="turn-2")
        self.assertEqual(panel.rows["session-a"].status_label.text(), "已完成")
        self.pet.handle_event("turn.started", session_id="session-a", turn_id="turn-3")
        self.assertEqual(len(panel.rows), 1)
        self.assertEqual(panel.rows["session-a"].name_label.text(), "Session 1")

    def test_session_title_updates_to_latest_prompt(self) -> None:
        self.pet.handle_event(
            "turn.started", "幫我製作桌寵面板", "session-a", "turn-1"
        )
        panel = self.pet.session_panel
        self.assertEqual(panel.rows["session-a"].title, "幫我製作桌寵面板")
        self.assertEqual(panel.rows["session-a"].name_label.text(), "幫我製作桌寵面板")
        self.app.processEvents()
        self.assertTrue(panel.rows["session-a"].name_label.isVisible())
        self.pet.handle_event("turn.completed", session_id="session-a", turn_id="turn-1")

        self.pet.handle_event("turn.started", "請再調整大小", "session-a", "turn-2")
        row = panel.rows["session-a"]
        self.assertEqual(row.name_label.text(), "請再調整大小")
        self.assertEqual(row.title, "請再調整大小")
        self.assertIn("請再調整大小", row.toolTip())

        self.pet.handle_event("turn.completed", session_id="session-a", turn_id="turn-2")
        panel.rows["session-a"].dismiss_button.click()
        self.pet.handle_event("turn.started", "請保留最新標題", "session-a", "turn-3")
        row = panel.rows["session-a"]
        self.assertEqual(row.name_label.text(), "請保留最新標題")
        self.assertEqual(row.title, "請保留最新標題")
        self.assertIn("請保留最新標題", row.toolTip())

    def test_working_directory_prefix_uses_directory_style(self) -> None:
        self.pet.handle_event(
            "turn.started",
            "codex_desktop_pet > 請調整顯示樣式",
            "session-a",
            "turn-1",
        )
        label = self.pet.session_panel.rows["session-a"].name_label
        self.assertEqual(label.text(), "codex_desktop_pet > 請調整顯示樣式")
        self.assertEqual(label.directory_prefix, "codex_desktop_pet")
        self.assertEqual(label.DIRECTORY_COLOR.name(), "#4E9426")

    def test_long_session_title_ends_with_three_dots(self) -> None:
        title = "A" * 26
        self.pet.session_panel.set_panel_width(600)
        self.pet.handle_event("turn.started", title, "session-a", "turn-1")
        row = self.pet.session_panel.rows["session-a"]
        self.assertEqual(row.name_label.text(), "A" * 25 + "...")
        self.assertEqual(row.title, title)
        self.assertIn(title, row.toolTip())

    def test_session_title_uses_available_width(self) -> None:
        panel = TurnPanel(self.pet)
        panel.set_turn(("session-test", "turn-1"), "思考中", title="測" * 25)
        panel.show()
        panel.set_panel_width(600)
        self.app.processEvents()
        row = panel.rows["session-test"]
        self.assertEqual(row.name_label.text(), "測" * 25)

        panel.set_panel_width(MIN_PANEL_WIDTH)
        self.app.processEvents()
        self.assertTrue(row.name_label.text().endswith("..."))
        self.assertLess(len(row.name_label.text()), 28)
        self.assertLessEqual(
            row.name_label.fontMetrics().horizontalAdvance(row.name_label.text()),
            row.name_label.width(),
        )
        panel.close()

    def test_dragging_panel_edges_changes_width(self) -> None:
        panel = TurnPanel(self.pet)
        panel.move(100, 100)
        panel.show()
        self.app.processEvents()
        changes: list[int] = []
        panel.width_changed.connect(changes.append)

        right = panel.right_resize_handle
        QTest.mousePress(right, Qt.MouseButton.LeftButton, pos=QPoint(4, 20))
        QTest.mouseMove(right, QPoint(104, 20))
        QTest.mouseRelease(right, Qt.MouseButton.LeftButton, pos=QPoint(4, 20))
        self.assertEqual(panel.width(), 430)
        self.assertEqual(changes, [430])

        right_edge = panel.geometry().right()
        left = panel.left_resize_handle
        QTest.mousePress(left, Qt.MouseButton.LeftButton, pos=QPoint(4, 20))
        QTest.mouseMove(left, QPoint(-56, 20))
        QTest.mouseRelease(left, Qt.MouseButton.LeftButton, pos=QPoint(4, 20))
        self.assertEqual(panel.width(), 490)
        self.assertEqual(panel.geometry().right(), right_edge)
        self.assertEqual(changes, [430, 490])
        panel.close()

    def test_session_row_layout_and_status_colors(self) -> None:
        self.pet.handle_event("turn.started", "請檢查目前的工作狀態", "session-a", "turn-1")
        panel = self.pet.session_panel
        row = panel.rows["session-a"]
        self.app.processEvents()
        self.assertGreaterEqual(panel.width(), MIN_PANEL_WIDTH)
        self.assertLessEqual(panel.width(), MAX_PANEL_WIDTH)
        self.assertGreaterEqual(row.height(), 60)
        self.assertGreaterEqual(panel.scroll_area.viewport().height(), row.height())
        self.assertLess(row.status_label.y(), row.name_label.y())
        self.assertLess(row.status_dot.x(), row.status_label.x())
        self.assertLess(row.status_label.x(), row.dismiss_button.x())
        self.assertEqual(row.status_label.text(), "思考中")
        self.assertEqual(row.status_dot.color.name(), "#2469b1")

        self.pet.handle_event("turn.completed", session_id="session-a", turn_id="turn-1")
        self.assertEqual(row.status_dot.color.name(), "#238044")
        self.pet.handle_event("turn.started", "接著繼續處理", "session-a", "turn-2")
        self.pet.handle_event("turn.cancelled", session_id="session-a", turn_id="turn-2")
        self.assertEqual(row.status_label.text(), "已取消")
        self.assertEqual(row.status_dot.color.name(), "#c43c3c")

    def test_panel_switches_to_left_at_right_edge(self) -> None:
        self.pet.session_offset = None
        screen = QApplication.primaryScreen()
        self.assertIsNotNone(screen)
        area = screen.availableGeometry()
        self.pet.move(QPoint(area.left() + 10, area.top() + 10))
        self.pet._position_session_panel()
        self.assertGreaterEqual(self.pet.session_panel.x(), self.pet.x() + self.pet.width())

        self.pet.move(QPoint(area.right() - self.pet.width(), area.top() + 10))
        self.pet._position_session_panel()
        self.assertLess(self.pet.session_panel.x(), self.pet.x())

    def test_session_end_retains_and_unlocks_unfinished_row(self) -> None:
        key = ("session-a", "turn-a")
        self.pet.handle_event("turn.started", session_id=key[0], turn_id=key[1])
        self.pet.handle_event("session.ended", session_id=key[0])
        row = self.pet.session_panel.rows[key[0]]
        self.assertEqual(row.status_label.text(), "已結束")
        self.assertTrue(row.dismiss_button.isEnabled())

    def test_left_click_toggles_panel_without_double_click_opening_settings(self) -> None:
        panel = self.pet.session_panel
        self.assertTrue(panel.isVisible())
        QTest.mouseClick(self.pet, Qt.MouseButton.LeftButton)
        self.assertFalse(panel.isVisible())
        QTest.qWait(QApplication.doubleClickInterval() + 20)
        self.assertFalse(panel.isVisible())

        QTest.mouseClick(self.pet, Qt.MouseButton.LeftButton)
        self.assertTrue(panel.isVisible())
        QTest.qWait(QApplication.doubleClickInterval() * 2 + 20)
        self.assertTrue(panel.isVisible())

        QTest.mouseDClick(self.pet, Qt.MouseButton.LeftButton)
        self.assertIsNone(self.pet.settings_panel)
        self.assertTrue(panel.isVisible())

    def test_double_click_restores_panel_state_after_first_click(self) -> None:
        panel = self.pet.session_panel
        QTest.mouseClick(self.pet, Qt.MouseButton.LeftButton)
        self.assertFalse(panel.isVisible())
        QTest.mouseDClick(self.pet, Qt.MouseButton.LeftButton)
        self.assertTrue(panel.isVisible())
        self.assertIsNone(self.pet.settings_panel)

    def test_drag_does_not_toggle_panel(self) -> None:
        class DragEvent:
            def __init__(self, position: QPoint):
                self.position = position

            def globalPosition(self) -> QPointF:
                return QPointF(self.position)

            def buttons(self):
                return Qt.MouseButton.LeftButton

            def accept(self) -> None:
                pass

        QTest.mousePress(self.pet, Qt.MouseButton.LeftButton)
        start = self.pet.drag_start_global
        self.assertIsNotNone(start)
        self.pet.mouseMoveEvent(DragEvent(start + QPoint(50, 0))) # type: ignore
        QTest.mouseRelease(self.pet, Qt.MouseButton.LeftButton)
        self.assertFalse(self.pet.panel_toggle_timer.isActive())
        self.assertTrue(self.pet.session_panel.isVisible())


if __name__ == "__main__":
    unittest.main()
