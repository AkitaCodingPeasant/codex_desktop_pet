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
        self.assertEqual(panel.rows[first[0]].status_label.text(), "工作中")
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

    def test_panel_switches_to_left_at_right_edge(self) -> None:
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

    def test_left_click_toggles_panel_without_changing_double_click(self) -> None:
        panel = self.pet.session_panel
        self.assertTrue(panel.isVisible())
        QTest.mouseClick(self.pet, Qt.MouseButton.LeftButton)
        self.assertFalse(panel.isVisible())
        QTest.qWait(QApplication.doubleClickInterval() + 20)
        self.assertFalse(panel.isVisible())

        QTest.mouseClick(self.pet, Qt.MouseButton.LeftButton)
        self.assertTrue(panel.isVisible())
        QTest.qWait(QApplication.doubleClickInterval() + 20)
        self.assertTrue(panel.isVisible())

        QTest.mouseDClick(self.pet, Qt.MouseButton.LeftButton)
        self.assertTrue(self.pet.settings_panel.isVisible())
        self.assertTrue(panel.isVisible())

    def test_double_click_restores_panel_state_after_first_click(self) -> None:
        panel = self.pet.session_panel
        QTest.mouseClick(self.pet, Qt.MouseButton.LeftButton)
        self.assertFalse(panel.isVisible())
        QTest.mouseDClick(self.pet, Qt.MouseButton.LeftButton)
        self.assertTrue(panel.isVisible())
        self.assertTrue(self.pet.settings_panel.isVisible())

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
        self.pet.mouseMoveEvent(DragEvent(start + QPoint(50, 0)))
        QTest.mouseRelease(self.pet, Qt.MouseButton.LeftButton)
        self.assertFalse(self.pet.panel_toggle_timer.isActive())
        self.assertTrue(self.pet.session_panel.isVisible())


if __name__ == "__main__":
    unittest.main()
