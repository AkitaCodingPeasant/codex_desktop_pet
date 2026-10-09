from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from desktop_pet.config import load_spritesheet_config
from desktop_pet.desktop_pet import DesktopPet, RESULT_CLIPS


def play_result_to_end(pet: DesktopPet, event_name: str) -> None:
    intro, repeat = RESULT_CLIPS[event_name]
    repeat_count = 1 if event_name == "turn.cancelled" else 3
    frame_count = (
        len(pet.config.animations[intro].frame_sequence)
        + repeat_count * len(pet.config.animations[repeat].frame_sequence)
    )
    for _ in range(frame_count - 1):
        pet.advance_frame()
        assert pet.state == "result"
    pet.advance_frame()


class ReplyBubbleTests(unittest.TestCase):
    def test_working_intro_then_repeat_until_tool_finishes(self) -> None:
        app = QApplication.instance() or QApplication([])
        with patch("desktop_pet.desktop_pet.keep_topmost"):
            pet = DesktopPet(load_spritesheet_config())
            try:
                self.assertEqual(pet.config.animations["working_intro"].row, 16)
                self.assertEqual(len(pet.config.animations["working_intro"].frame_sequence), 59)
                self.assertEqual(pet.config.animations["working_repeat"].row, 17)
                self.assertEqual(len(pet.config.animations["working_repeat"].frame_sequence), 60)
                pet.handle_event("turn.started", session_id="session-a", turn_id="turn-a")
                pet.handle_event("tool.started", session_id="session-a", turn_id="turn-a")
                self.assertEqual((pet.state, pet.animation_name), ("working", "working_intro"))
                for _ in range(59):
                    pet.advance_frame()
                self.assertEqual((pet.state, pet.animation_name), ("working", "working_repeat"))
                for _ in range(60):
                    pet.advance_frame()
                self.assertEqual((pet.state, pet.animation_name, pet.frame_index),
                                 ("working", "working_repeat", 0))
                pet.handle_event("turn.in_progress", session_id="session-a", turn_id="turn-a")
                self.assertEqual((pet.state, pet.animation_name), ("thinking", "thinking_1_1"))
            finally:
                pet.close()
        self.assertIsNotNone(app)

    def test_working_priority_and_overlapping_tools(self) -> None:
        app = QApplication.instance() or QApplication([])
        with patch("desktop_pet.desktop_pet.keep_topmost"):
            pet = DesktopPet(load_spritesheet_config())
            try:
                pet.handle_event("turn.started", session_id="session-a", turn_id="turn-a")
                pet.handle_event("turn.started", session_id="session-b", turn_id="turn-b")
                pet.handle_event("tool.started", session_id="session-b", turn_id="turn-b")
                self.assertEqual(pet.state, "working")
                pet.handle_event("tool.started", session_id="session-b", turn_id="turn-b")
                self.assertEqual(pet.animation_name, "working_intro")
                pet.handle_event("turn.in_progress", session_id="session-b", turn_id="turn-b")
                self.assertEqual(pet.state, "working")
                pet.handle_event("action_required", session_id="session-a", turn_id="turn-a")
                self.assertEqual(pet.state, "asking")
                pet.handle_event("user_input_completed", session_id="session-a", turn_id="turn-a")
                self.assertEqual(pet.state, "working")
                pet.handle_event("turn.in_progress", session_id="session-b", turn_id="turn-b")
                self.assertEqual(pet.state, "thinking")
            finally:
                pet.close()
        self.assertIsNotNone(app)

    def test_completion_shows_reply_until_result_finishes(self) -> None:
        app = QApplication.instance() or QApplication([])
        with patch("desktop_pet.desktop_pet.keep_topmost"):
            pet = DesktopPet(load_spritesheet_config())
            try:
                pet.show()
                pet.handle_event("turn.completed", "這是一段測試回覆")
                self.assertTrue(pet.reply_bubble.isVisible())
                self.assertEqual(pet.reply_bubble.text(), "這是一段測試回覆")
                self.assertTrue(pet.reply_timer.isActive())
                pet.handle_event("turn.in_progress")
                self.assertEqual(pet.state, "result")
                self.assertTrue(pet.reply_bubble.isVisible())
                play_result_to_end(pet, "turn.completed")
                self.assertEqual(pet.state, "thinking")
                self.assertFalse(pet.reply_bubble.isVisible())
            finally:
                pet.close()
        self.assertIsNotNone(app)

    def test_reply_bubble_fits_short_and_long_text_without_old_size(self) -> None:
        app = QApplication.instance() or QApplication([])
        with patch("desktop_pet.desktop_pet.keep_topmost"):
            pet = DesktopPet(load_spritesheet_config())
            try:
                pet.show()
                pet.reply_bubble.setText("短")
                pet.reply_bubble.show()
                app.processEvents()
                short_size = pet.reply_bubble.size()
                self.assertLess(short_size.width(), 344)

                pet.reply_bubble.setText("這是一段比較長的回覆。" * 10)
                app.processEvents()
                long_size = pet.reply_bubble.size()
                self.assertEqual(long_size.width(), 344)
                self.assertGreater(long_size.height(), short_size.height())
                label = pet.reply_bubble.message_label
                self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()))

                pet.reply_bubble.setText("短")
                app.processEvents()
                self.assertEqual(pet.reply_bubble.size(), short_size)
            finally:
                pet.close()
        self.assertIsNotNone(app)

    def test_panel_counts_distinct_active_turns(self) -> None:
        app = QApplication.instance() or QApplication([])
        with patch("desktop_pet.desktop_pet.keep_topmost") as keep_topmost_mock:
            pet = DesktopPet(load_spritesheet_config())
            try:
                pet.show()
                pet.handle_event("turn.in_progress", session_id="session-a", turn_id="turn-a")
                pet.handle_event("turn.in_progress", session_id="session-a", turn_id="turn-a")
                pet.handle_event("turn.in_progress", session_id="session-b", turn_id="turn-b")
                keep_topmost_mock.reset_mock()
                pet.open_settings()
                keep_topmost_mock.assert_any_call(int(pet.winId()))
                self.assertIsNone(pet.settings_panel.parent())
                self.assertFalse(
                    pet.settings_panel.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
                )
                self.assertEqual(pet.settings_panel.active_count_value.text(), "2")
                self.assertEqual(pet.settings_panel.status_value.text(), "工作中")
                pet.handle_event("action_required", session_id="session-b", turn_id="turn-b")
                self.assertEqual(pet.settings_panel.status_value.text(), "等待授權")
                pet.handle_event("turn.completed", session_id="session-b", turn_id="turn-b")
                self.assertEqual(pet.settings_panel.active_count_value.text(), "1")
                self.assertEqual(pet.settings_panel.status_value.text(), "剛完成")
                play_result_to_end(pet, "turn.completed")
                self.assertEqual(pet.settings_panel.status_value.text(), "工作中")
                pet.handle_event("turn.cancelled", session_id="session-a", turn_id="turn-a")
                self.assertEqual(pet.settings_panel.active_count_value.text(), "0")
                self.assertEqual(pet.settings_panel.status_value.text(), "已取消")
            finally:
                pet.close()
        self.assertIsNotNone(app)

    def test_user_question_plays_asking_until_work_resumes(self) -> None:
        app = QApplication.instance() or QApplication([])
        with patch("desktop_pet.desktop_pet.keep_topmost"):
            pet = DesktopPet(load_spritesheet_config())
            try:
                pet.handle_event("turn.started", session_id="session-a", turn_id="turn-a")
                pet.handle_event("user_input_requested", session_id="session-a", turn_id="turn-a")
                self.assertEqual(pet.state, "asking")
                self.assertEqual(pet.animation_name, "asking_intro")
                self.assertEqual(pet.status_text, "等待回覆")
                pet.handle_event("turn.in_progress", session_id="session-a", turn_id="turn-a")
                self.assertEqual(pet.state, "thinking")
            finally:
                pet.close()
        self.assertIsNotNone(app)

    def test_completed_turn_finishes_animation_before_other_turn_resumes(self) -> None:
        app = QApplication.instance() or QApplication([])
        with patch("desktop_pet.desktop_pet.keep_topmost"):
            pet = DesktopPet(load_spritesheet_config())
            try:
                pet.handle_event("turn.started", session_id="session-a", turn_id="turn-a")
                pet.handle_event("turn.started", session_id="session-b", turn_id="turn-b")
                pet.handle_event("turn.completed", "A 的回覆", "session-a", "turn-a")
                self.assertEqual(pet.active_turns, {("session-b", "turn-b"): "thinking"})
                self.assertEqual(pet.animation_name, "success_intro")
                self.assertEqual(pet.status_text, "剛完成")
                pet.handle_event("turn.in_progress", session_id="session-b", turn_id="turn-b")
                self.assertEqual(pet.state, "result")
                play_result_to_end(pet, "turn.completed")
                self.assertEqual(pet.state, "thinking")
                self.assertEqual(pet.animation_name, "thinking_1_1")
            finally:
                pet.close()
        self.assertIsNotNone(app)

    def test_followup_turn_waits_for_completed_animation(self) -> None:
        app = QApplication.instance() or QApplication([])
        with patch("desktop_pet.desktop_pet.keep_topmost"):
            pet = DesktopPet(load_spritesheet_config())
            try:
                pet.handle_event("turn.started", session_id="session-a", turn_id="first")
                pet.handle_event("turn.completed", "第一回覆", "session-a", "first")
                pet.handle_event("turn.started", session_id="session-a", turn_id="followup")
                self.assertEqual(pet.state, "result")
                self.assertEqual(pet.reply_bubble.text(), "第一回覆")
                play_result_to_end(pet, "turn.completed")
                self.assertEqual(pet.state, "thinking")
                self.assertEqual(pet.active_turns, {("session-a", "followup"): "thinking"})
            finally:
                pet.close()
        self.assertIsNotNone(app)

    def test_multiple_results_play_in_arrival_order(self) -> None:
        app = QApplication.instance() or QApplication([])
        with patch("desktop_pet.desktop_pet.keep_topmost"):
            pet = DesktopPet(load_spritesheet_config())
            try:
                pet.handle_event("turn.started", session_id="session-a", turn_id="turn-a")
                pet.handle_event("turn.started", session_id="session-b", turn_id="turn-b")
                pet.handle_event("turn.completed", "A 的回覆", "session-a", "turn-a")
                pet.handle_event("turn.completed", "B 的回覆", "session-b", "turn-b")
                self.assertEqual(pet.reply_bubble.text(), "A 的回覆")
                self.assertEqual(pet.pending_results, [("turn.completed", "B 的回覆")])
                play_result_to_end(pet, "turn.completed")
                self.assertEqual(pet.state, "result")
                self.assertEqual(pet.animation_name, "success_intro")
                self.assertEqual(pet.reply_bubble.text(), "B 的回覆")
                play_result_to_end(pet, "turn.completed")
                self.assertEqual(pet.state, "idle")
            finally:
                pet.close()
        self.assertIsNotNone(app)

    def test_new_turn_clears_unfinished_turn_in_same_session(self) -> None:
        app = QApplication.instance() or QApplication([])
        with patch("desktop_pet.desktop_pet.keep_topmost"):
            pet = DesktopPet(load_spritesheet_config())
            try:
                pet.handle_event("turn.started", session_id="session-a", turn_id="old")
                pet.handle_event("turn.started", session_id="session-b", turn_id="other")
                pet.handle_event("turn.started", session_id="session-a", turn_id="new")
                self.assertEqual(
                    pet.active_turns,
                    {("session-b", "other"): "thinking", ("session-a", "new"): "thinking"},
                )
                pet.handle_event("turn.completed", session_id="session-a", turn_id="new")
                self.assertEqual(pet.active_turns, {("session-b", "other"): "thinking"})
                pet.handle_event("turn.completed", session_id="session-b", turn_id="other")
                self.assertEqual(pet.active_turns, {})
                self.assertEqual(pet.state, "result")
            finally:
                pet.close()
        self.assertIsNotNone(app)

    def test_late_tool_event_does_not_restart_finished_turn(self) -> None:
        app = QApplication.instance() or QApplication([])
        with patch("desktop_pet.desktop_pet.keep_topmost"):
            pet = DesktopPet(load_spritesheet_config())
            try:
                pet.handle_event("turn.started", session_id="session-a", turn_id="turn-a")
                pet.handle_event("turn.completed", session_id="session-a", turn_id="turn-a")
                pet.handle_event("turn.in_progress", session_id="session-a", turn_id="turn-a")
                self.assertEqual(pet.active_turns, {})
                self.assertEqual(pet.state, "result")
            finally:
                pet.close()
        self.assertIsNotNone(app)

    def test_late_previous_turn_events_do_not_replace_current_reply(self) -> None:
        app = QApplication.instance() or QApplication([])
        with patch("desktop_pet.desktop_pet.keep_topmost"):
            pet = DesktopPet(load_spritesheet_config())
            try:
                pet.show()
                pet.handle_event("turn.started", session_id="session-a", turn_id="old")
                pet.handle_event("turn.started", session_id="session-a", turn_id="new")
                pet.handle_event("turn.completed", "上一則回覆", "session-a", "old")
                pet.handle_event("turn.in_progress", session_id="session-a", turn_id="old")
                self.assertEqual(pet.active_turns, {("session-a", "new"): "thinking"})
                self.assertFalse(pet.reply_bubble.isVisible())
                pet.handle_event("turn.completed", "目前回覆", "session-a", "new")
                self.assertEqual(pet.reply_bubble.text(), "目前回覆")
                pet.handle_event("turn.completed", "上一則回覆", "session-a", "old")
                self.assertEqual(pet.reply_bubble.text(), "目前回覆")
            finally:
                pet.close()
        self.assertIsNotNone(app)

    def test_session_end_removes_unfinished_turn(self) -> None:
        app = QApplication.instance() or QApplication([])
        with patch("desktop_pet.desktop_pet.keep_topmost"):
            pet = DesktopPet(load_spritesheet_config())
            try:
                pet.handle_event("turn.started", session_id="session-a", turn_id="turn-a")
                pet.handle_event("session.ended", session_id="session-a")
                self.assertEqual(pet.active_turns, {})
                self.assertEqual(pet.state, "idle")
            finally:
                pet.close()
        self.assertIsNotNone(app)



if __name__ == "__main__":
    unittest.main()
