from __future__ import annotations

import math
import os
import random
import re
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from desktop_pet.config import SpriteSheetConfig
from desktop_pet.hook_bridge import send_event
from desktop_pet.settings_panel import SettingsPanel
from desktop_pet.topmost import keep_topmost


IDLE_CLIPS = (("idle_1",), ("idle_2_1", "idle_2_2"), ("idle_3",), ("idle_4",))
THINKING_CLIPS = ("thinking_1_1", "thinking_1_2")
RESULT_CLIPS = {
    "turn.completed": ("success_intro", "success_repeat"),
    "turn.failed": ("failed_intro", "failed_repeat"),
    "turn.cancelled": ("cancelled_intro", "cancelled_repeat"),
}
BOTTOM_GAP_PX = 0


class ReplyBubble(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.max_reply_width = 344
        font_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        for filename in ("NotoSansTC-VF.ttf", "msjh.ttc"):
            font_id = QFontDatabase.addApplicationFont(str(font_dir / filename))
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                self.setFont(QFont(families[0], 10))
                break

        outer = QVBoxLayout(self)
        self.outer_layout = outer
        outer.setContentsMargins(8, 6, 8, 10)
        card = QFrame()
        self.reply_card = card
        card.setObjectName("replyCard")
        outer.addWidget(card)

        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(20, 35, 58, 55))
        card.setGraphicsEffect(shadow)

        content = QVBoxLayout(card)
        self.content_layout = content
        content.setContentsMargins(14, 10, 14, 12)
        content.setSpacing(8)
        header = QHBoxLayout()
        self.header_layout = header
        header.setSpacing(8)
        indicator = QLabel()
        indicator.setObjectName("replyIndicator")
        indicator.setFixedSize(8, 8)
        heading = QLabel("CODEX 回覆")
        heading.setObjectName("replyHeading")
        header.addWidget(indicator)
        header.addWidget(heading)
        header.addStretch()
        content.addLayout(header)

        self.message_label = QLabel()
        self.message_label.setObjectName("replyMessage")
        self.message_label.setTextFormat(Qt.TextFormat.PlainText)
        self.message_label.setWordWrap(True)
        content.addWidget(self.message_label)

        self.change_summary = QWidget()
        change_row = QHBoxLayout(self.change_summary)
        change_row.setContentsMargins(0, 0, 0, 0)
        change_row.setSpacing(8)
        self.change_summary_label = QLabel()
        self.change_summary_label.setObjectName("changeSummary")
        self.change_summary_label.setTextFormat(Qt.TextFormat.PlainText)
        self.added_lines_label = QLabel()
        self.added_lines_label.setObjectName("addedLines")
        self.removed_lines_label = QLabel()
        self.removed_lines_label.setObjectName("removedLines")
        for label in (self.change_summary_label, self.added_lines_label, self.removed_lines_label):
            change_row.addWidget(label)
        self.change_summary.hide()
        content.addWidget(self.change_summary)

        self.setStyleSheet("""
            QFrame#replyCard {
                background: #ffffff;
                border: 1px solid #dbe5ee;
                border-radius: 18px;
            }
            QLabel { background: transparent; border: none; }
            QLabel#replyIndicator { background: #22b8a0; border-radius: 4px; }
            QLabel#replyHeading {
                color: #52687d;
                font-family: "Noto Sans TC", "Microsoft JhengHei", "Segoe UI";
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#replyMessage {
                color: #172b3d;
                font-family: "Noto Sans TC", "Microsoft JhengHei", "Segoe UI";
                font-size: 14px;
            }
            QLabel#changeSummary {
                color: #6b7785;
                font-family: "Noto Sans TC", "Microsoft JhengHei", "Segoe UI";
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#addedLines {
                color: #168a54;
                font-family: "Noto Sans TC", "Microsoft JhengHei", "Segoe UI";
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#removedLines {
                color: #c94b58;
                font-family: "Noto Sans TC", "Microsoft JhengHei", "Segoe UI";
                font-size: 12px;
                font-weight: 700;
            }
        """)

    def setText(self, message: str) -> None:
        lines = message.rsplit("\n", 1)
        summary = re.fullmatch(r"(?:已)?變更 (\d+) 個檔案 \+(\d+) -(\d+)", lines[-1])
        reply = lines[0] if summary and len(lines) == 2 else ("" if summary else message)
        self.message_label.setText(reply)
        self.message_label.setHidden(not reply)
        self.change_summary_label.setText(f"已變更 {summary[1]} 個檔案" if summary else "")
        self.added_lines_label.setText(f"+{summary[2]}" if summary else "")
        self.removed_lines_label.setText(f"-{summary[3]}" if summary else "")
        self.change_summary.setHidden(not summary)
        visible_count = bool(reply) + bool(summary)
        outer_margin = self.outer_layout.contentsMargins()
        content_margin = self.content_layout.contentsMargins()
        border = 2 * self.reply_card.frameWidth()
        horizontal_padding = (
            outer_margin.left() + outer_margin.right()
            + content_margin.left() + content_margin.right() + border
        )
        vertical_padding = (
            outer_margin.top() + outer_margin.bottom()
            + content_margin.top() + content_margin.bottom() + border
            + self.header_layout.sizeHint().height()
        )
        width = min(
            self.max_reply_width,
            max(
                self.header_layout.sizeHint().width(),
                self.message_label.sizeHint().width() if reply else 0,
                self.change_summary.sizeHint().width() if summary else 0,
            )
            + horizontal_padding,
        )
        height = vertical_padding + self.content_layout.spacing() * visible_count
        if reply:
            height += self.message_label.heightForWidth(width - horizontal_padding)
        if summary:
            height += self.change_summary.sizeHint().height()
        self.setFixedSize(width, height)
        self.content_layout.invalidate()
        self.outer_layout.invalidate()
        self.outer_layout.activate()

    def text(self) -> str:
        return self.message_label.text()


class DesktopPet(QWidget):
    def __init__(self, config: SpriteSheetConfig):
        super().__init__()
        self.config = config
        self.spritesheet = QPixmap(str(config.image_path))
        if self.spritesheet.isNull():
            raise FileNotFoundError(f"Could not load spritesheet: {config.image_path}")

        self.animation_name = ""
        self.frame_index = 0
        self.drag_position: QPoint | None = None
        self.state = "idle"
        self.status_text = "閒置"
        self.active_turns: dict[tuple[str, str], str] = {}
        self.active_tool_counts: dict[tuple[str, str], int] = {}
        self.finished_turns: set[tuple[str, str]] = set()
        self.current_turns: dict[str, str] = {}
        self.pending_results: list[tuple[str, str]] = []
        self.clip_queue: list[str] = []
        self.repeat_clip: str | None = None
        self.repeats_left: int | None = None
        self.settings = QSettings("DesktopPet", "DesktopPet")
        self.scale_percent = self._saved_number("scale_percent", 100, 50, 200)
        default_fps = next(iter(config.animations.values())).fps
        self.fps = self._saved_number("fps", default_fps, 4, 60)
        self.settings_panel: SettingsPanel | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(
            round(config.frame_width * self.scale_percent / 100),
            round(config.frame_height * self.scale_percent / 100),
        )

        self.label = QLabel(self)
        self.label.setFixedSize(self.size())
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.reply_bubble = ReplyBubble(self)
        self.reply_timer = QTimer(self)
        self.reply_timer.setSingleShot(True)
        self.reply_timer.timeout.connect(self.reply_bubble.hide)

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.advance_frame)
        self.working_timer = QTimer(self)
        self.working_timer.setSingleShot(True)
        self.working_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.working_timer.timeout.connect(self._finish_working_window)
        self.topmost_timer = QTimer(self)
        self.topmost_timer.timeout.connect(self.keep_on_top)
        self.topmost_timer.start(1000)
        self._next_idle()

    def _saved_number(self, key: str, default: int, minimum: int, maximum: int) -> int:
        saved_value = self.settings.value(key, default)
        try:
            value = (
                int(saved_value)
                if isinstance(saved_value, (str, int, float))
                else default
            )
        except (TypeError, ValueError, OverflowError):
            value = default
        return max(minimum, min(maximum, value))

    def set_scale_percent(self, value: int) -> None:
        self.scale_percent = value
        self.setFixedSize(
            round(self.config.frame_width * value / 100),
            round(self.config.frame_height * value / 100),
        )
        self.label.setFixedSize(self.size())
        self.move(self._clamp_to_single_screen(self.pos()))
        self._position_reply_bubble()
        self.show_current_frame()
        self.settings.setValue("scale_percent", value)

    def set_fps(self, value: int) -> None:
        self.fps = value
        self.animation_timer.setInterval(max(1, round(1000 / value)))
        self.settings.setValue("fps", value)

    def open_settings(self) -> None:
        if self.settings_panel is None:
            preview = self.spritesheet.copy(
                0, 0, self.config.frame_width, self.config.frame_height
            )
            panel = SettingsPanel(self.scale_percent, self.fps, preview)
            panel.scale_changed.connect(self.set_scale_percent)
            panel.fps_changed.connect(self.set_fps)
            panel.hook_test_requested.connect(send_event)
            panel.stop_requested.connect(QApplication.quit)
            self.settings_panel = panel
        self._update_panel_status()
        self.settings_panel.show()
        self.settings_panel.raise_()
        self.settings_panel.activateWindow()
        self.keep_on_top()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.keep_on_top)

    def closeEvent(self, event) -> None:
        if self.settings_panel is not None:
            self.settings_panel.close()
        super().closeEvent(event)

    def keep_on_top(self) -> None:
        if self.isVisible() and not self.isMinimized():
            keep_topmost(int(self.winId()))
            if self.reply_bubble.isVisible():
                keep_topmost(int(self.reply_bubble.winId()))

    def _position_reply_bubble(self) -> None:
        if not self.reply_bubble.isVisible():
            return
        center = self.frameGeometry().center()
        screen = QApplication.screenAt(center) or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        x = max(area.left(), min(center.x() - self.reply_bubble.width() // 2,
                                 area.right() - self.reply_bubble.width() + 1))
        above = self.y() - self.reply_bubble.height() - 8
        below = self.y() + self.height() + 8
        y = above if above >= area.top() else min(below, area.bottom() - self.reply_bubble.height() + 1)
        self.reply_bubble.move(x, y)

    def _show_reply(self, message: str) -> None:
        self.reply_bubble.setText(message)
        self.reply_bubble.show()
        self._position_reply_bubble()
        self.keep_on_top()
        self.reply_timer.start(6000)

    @staticmethod
    def _distance_to_rect(point: QPoint, rect: QRect) -> float:
        dx = max(rect.left() - point.x(), 0, point.x() - rect.right())
        dy = max(rect.top() - point.y(), 0, point.y() - rect.bottom())
        return math.hypot(dx, dy)

    def _clamp_to_single_screen(self, position: QPoint) -> QPoint:
        screens = QApplication.screens()
        if not screens:
            return position

        center = QPoint(position.x() + self.width() // 2, position.y() + self.height() // 2)
        screen = QApplication.screenAt(center)
        if screen is None:
            screen = min(screens, key=lambda item: self._distance_to_rect(center, item.geometry()))

        geometry = screen.availableGeometry()
        max_x = geometry.left() + max(0, geometry.width() - self.width())
        max_y = geometry.top() + max(0, geometry.height() - self.height() - BOTTOM_GAP_PX)
        return QPoint(
            min(max(position.x(), geometry.left()), max_x),
            min(max(position.y(), geometry.top()), max_y),
        )

    def _update_panel_status(self) -> None:
        if self.settings_panel is not None:
            self.settings_panel.set_work_status(self.status_text, len(self.active_turns))

    def _play_active_state(self) -> None:
        asking = any(status in {"asking", "asking_user"} for status in self.active_turns.values())
        working = any(self.active_tool_counts.values()) or self.working_timer.isActive()
        target = "asking" if asking else "working" if working else "thinking"
        self.status_text = (
            "等待授權" if "asking" in self.active_turns.values()
            else "等待回覆" if asking else "操作工具中" if working else "工作中"
        )
        self._update_panel_status()
        if self.state == target:
            return
        self.state = target
        if asking:
            self._play_sequence(("asking_intro",), repeat="asking_repeat")
        elif working:
            self._play_sequence(("working_intro",), repeat="working_repeat")
        else:
            self._play_sequence(THINKING_CLIPS)

    def _refresh_active_state(self) -> None:
        if self.state == "result":
            self._update_panel_status()
        else:
            self._play_active_state()

    def _finish_working_window(self) -> None:
        if self.state == "result":
            return
        if self.active_turns:
            self._play_active_state()
        else:
            self._next_idle()

    def _start_next_result(self) -> None:
        event_name, message = self.pending_results.pop(0)
        self.reply_timer.stop()
        self.reply_bubble.hide()
        if event_name == "turn.completed" and message:
            self._show_reply(message)
        self.state = "result"
        self.status_text = {
            "turn.completed": "剛完成",
            "turn.failed": "執行失敗",
            "turn.cancelled": "已取消",
        }[event_name]
        self._update_panel_status()
        intro, repeat = RESULT_CLIPS[event_name]
        self._play_sequence(
            (intro,), repeat=repeat, repeats=1 if event_name == "turn.cancelled" else 3
        )

    def _finish_result(self) -> None:
        if self.pending_results:
            self._start_next_result()
        elif self.active_turns:
            self.reply_timer.stop()
            self.reply_bubble.hide()
            self._play_active_state()
        else:
            self._next_idle()

    def handle_event(
        self, event_name: str, message: str = "", session_id: str = "", turn_id: str = ""
    ) -> None:
        key = (session_id, turn_id)
        if session_id and turn_id and event_name != "turn.started":
            current_turn = self.current_turns.get(session_id)
            if current_turn is not None and current_turn != turn_id:
                return
        if event_name in {"turn.started", "turn.in_progress", "tool.started", "action_required", "user_input_requested", "user_input_completed"}:
            if key in self.finished_turns:
                return
        if event_name == "turn.started":
            if session_id and turn_id:
                previous_turn = self.current_turns.get(session_id)
                if previous_turn and previous_turn != turn_id:
                    self.finished_turns.add((session_id, previous_turn))
                self.current_turns[session_id] = turn_id
            # A session has only one foreground turn. Drop a previous turn whose
            # completion hook was missed so it cannot keep the pet busy forever.
            self.active_turns = {
                active_key: status
                for active_key, status in self.active_turns.items()
                if active_key[0] != session_id
            }
            self.active_tool_counts = {
                active_key: count
                for active_key, count in self.active_tool_counts.items()
                if active_key[0] != session_id
            }
            self.active_turns[key] = "thinking"
            if self.state != "result":
                self.reply_timer.stop()
                self.reply_bubble.hide()
            self._refresh_active_state()
        elif event_name == "tool.started":
            if self.active_turns.get(key) != "asking":
                self.active_turns[key] = "thinking"
            self.active_tool_counts[key] = self.active_tool_counts.get(key, 0) + 1
            self.working_timer.start(2000)
            if self.state != "result":
                self.reply_timer.stop()
                self.reply_bubble.hide()
            self._refresh_active_state()
        elif event_name == "turn.in_progress":
            self.active_turns[key] = "thinking"
            if key in self.active_tool_counts:
                self.active_tool_counts[key] -= 1
                if self.active_tool_counts[key] <= 0:
                    del self.active_tool_counts[key]
            if self.state != "result":
                self.reply_timer.stop()
                self.reply_bubble.hide()
            self._refresh_active_state()
        elif event_name == "user_input_completed":
            self.active_turns[key] = "thinking"
            self._refresh_active_state()
        elif event_name == "action_required":
            self.active_turns[key] = "asking"
            self._refresh_active_state()
        elif event_name == "user_input_requested":
            self.active_turns[key] = "asking_user"
            self._refresh_active_state()
        elif event_name in RESULT_CLIPS:
            if key in self.finished_turns:
                return
            if session_id and turn_id:
                self.finished_turns.add(key)
                if len(self.finished_turns) > 1000:
                    self.finished_turns.pop()
            self.active_turns.pop(key, None)
            self.active_tool_counts.pop(key, None)
            if not self.active_tool_counts:
                self.working_timer.stop()
            self.pending_results.append((event_name, message))
            if self.state == "result":
                self._update_panel_status()
            else:
                self._start_next_result()
        elif event_name == "session.ended":
            previous_turn = self.current_turns.pop(session_id, None)
            if previous_turn:
                self.finished_turns.add((session_id, previous_turn))
            self.active_turns = {
                active_key: status
                for active_key, status in self.active_turns.items()
                if active_key[0] != session_id
            }
            self.active_tool_counts = {
                active_key: count
                for active_key, count in self.active_tool_counts.items()
                if active_key[0] != session_id
            }
            if not self.active_tool_counts:
                self.working_timer.stop()
            if self.state == "result":
                self._update_panel_status()
            elif self.active_turns:
                self._play_active_state()
            else:
                self._next_idle()

    def _play_sequence(
        self, clips: tuple[str, ...], repeat: str | None = None, repeats: int | None = None
    ) -> None:
        self.clip_queue = list(clips)
        self.repeat_clip = repeat
        self.repeats_left = repeats
        self._play_next_clip()

    def _next_idle(self) -> None:
        self.state = "idle"
        self.status_text = "閒置"
        self._update_panel_status()
        self._play_sequence(random.choice(IDLE_CLIPS))

    def _play_next_clip(self) -> None:
        if self.clip_queue:
            name = self.clip_queue.pop(0)
        elif self.repeat_clip is not None:
            if self.repeats_left == 0:
                if self.state == "result":
                    self._finish_result()
                else:
                    self._next_idle()
                return
            if self.repeats_left is not None:
                self.repeats_left -= 1
            name = self.repeat_clip
        elif self.state == "thinking":
            self.clip_queue = list(THINKING_CLIPS)
            self._play_next_clip()
            return
        elif self.state == "result":
            self._finish_result()
            return
        else:
            self._next_idle()
            return

        self.animation_name = name
        self.frame_index = 0
        self.animation_timer.start(max(1, round(1000 / self.fps)))
        self.show_current_frame()

    def advance_frame(self) -> None:
        animation = self.config.animations[self.animation_name]
        self.frame_index += 1
        if self.frame_index >= len(animation.frame_sequence):
            self._play_next_clip()
        else:
            self.show_current_frame()

    def show_current_frame(self) -> None:
        animation = self.config.animations[self.animation_name]
        frame_number = animation.frame_sequence[self.frame_index]
        frame = self.spritesheet.copy(
            frame_number * self.config.frame_width,
            (animation.row - 1) * self.config.frame_height,
            self.config.frame_width,
            self.config.frame_height,
        )
        if self.scale_percent != 100:
            frame = frame.scaled(
                self.size(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self.label.setPixmap(frame)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = None
            self.open_settings()
            event.accept()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self.drag_position is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(self._clamp_to_single_screen(event.globalPosition().toPoint() - self.drag_position))
            self._position_reply_bubble()
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = None
            event.accept()

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        exit_action = menu.addAction("Exit")
        if menu.exec(event.globalPos()) == exit_action:
            QApplication.quit()
