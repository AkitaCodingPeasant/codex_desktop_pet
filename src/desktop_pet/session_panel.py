from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPen,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


TERMINAL_STATUSES = {
    "turn.completed": "已完成",
    "turn.failed": "執行失敗",
    "turn.cancelled": "已取消",
}
EVENT_STATUSES = {
    "turn.started": "思考中",
    "turn.in_progress": "思考中",
    "tool.started": "調用工具中",
    "action_required": "等待授權",
    "user_input_requested": "等待回覆",
    "user_input_completed": "思考中",
    **TERMINAL_STATUSES,
}
DEFAULT_PANEL_WIDTH = 330
MIN_PANEL_WIDTH = 220
MAX_PANEL_WIDTH = 800
MAX_TITLE_CHARS = 100
PANEL_HEIGHT_BASE = 54
PANEL_ROW_HEIGHT = 54
MAX_VISIBLE_ROWS = 7

class DismissButton(QPushButton):
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.isEnabled():
            fill = "#d2e0e9" if self.underMouse() else "#e3ebf1"
            border, cross = "#c5d5e1", "#52687d"
        else:
            fill, border, cross = "#f3f7fa", "#d8e3eb", "#aebcc8"
        painter.setBrush(QColor(fill))
        painter.setPen(QPen(QColor(border), 1.2))
        painter.drawEllipse(QRectF(0.75, 0.75, self.width() - 1.5, self.height() - 1.5))
        center = QPointF(self.width() / 2, self.height() / 2)
        painter.setPen(QPen(QColor(cross), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(center + QPointF(-2, -2), center + QPointF(2, 2))
        painter.drawLine(center + QPointF(-2, 2), center + QPointF(2, -2))
        painter.end()


class StatusDot(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.color = QColor("#2469b1")
        self.setFixedSize(8, 8)

    def set_color(self, color: str) -> None:
        self.color = QColor(color)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.color)
        painter.drawEllipse(QRectF(0, 0, 8, 8))
        painter.end()


class SessionTitleLabel(QLabel):
    DIRECTORY_COLOR = QColor("#016AA7")
    DIRECTORY_COLOR = QColor("#5f6368")
    PROMPT_COLOR = QColor("#5f6368")

    def __init__(self, text: str):
        super().__init__(text)
        self.directory_prefix = ""

    def set_directory_prefix(self, prefix: str) -> None:
        self.directory_prefix = prefix
        self.update()

    def display_width(self, text: str) -> int:
        directory_length = min(len(self.directory_prefix), len(text))
        directory_font = self.font()
        directory_font.setBold(True)
        prompt_font = self.font()
        prompt_font.setBold(False)
        return (
            QFontMetrics(directory_font).horizontalAdvance(text[:directory_length])
            + QFontMetrics(prompt_font).horizontalAdvance(text[directory_length:])
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        text = self.text()
        if not self.directory_prefix or not text.startswith(self.directory_prefix):
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        bounds = self.contentsRect()
        directory_text = text[:len(self.directory_prefix)]
        prompt_text = text[len(directory_text):]

        directory_font = self.font()
        directory_font.setBold(True)
        painter.setFont(directory_font)
        painter.setPen(self.DIRECTORY_COLOR)
        directory_width = painter.fontMetrics().horizontalAdvance(directory_text)
        painter.drawText(
            bounds,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            directory_text,
        )

        prompt_font = self.font()
        prompt_font.setBold(False)
        painter.setFont(prompt_font)
        painter.setPen(self.PROMPT_COLOR)
        prompt_bounds = bounds.adjusted(directory_width, 0, 0, 0)
        painter.drawText(
            prompt_bounds,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            prompt_text,
        )
        painter.end()


class SessionRow(QFrame):
    dismiss_requested = Signal(object)

    def __init__(self, session_id: str, number: int):
        super().__init__()
        self.session_id = session_id
        self.number = number
        self.turn_id = ""
        self.title = ""
        self.terminal = False
        self.setObjectName("sessionRow")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 3, 8, 3)
        layout.setSpacing(2)
        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        self.name_label = SessionTitleLabel(f"Session {number}")
        self.name_label.setObjectName("sessionName")
        self.name_label.setTextFormat(Qt.TextFormat.PlainText)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.name_label.installEventFilter(self)
        self.status_label = QLabel()
        self.status_label.setObjectName("turnStatus")
        self.status_dot = StatusDot()
        self.dismiss_button = DismissButton()
        self.dismiss_button.setObjectName("dismissSession")
        self.dismiss_button.setToolTip("隱藏這個 Session")
        self.dismiss_button.setFixedSize(20, 20)
        self.dismiss_button.setEnabled(False)
        self.dismiss_button.clicked.connect(lambda: self.dismiss_requested.emit(self.session_id))
        top_row.addWidget(self.status_dot, alignment=Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(self.status_label)
        top_row.addStretch()
        top_row.addWidget(self.dismiss_button)
        layout.addLayout(top_row)
        layout.addWidget(self.name_label)
        self.setMinimumHeight(50)
        self.set_status("思考中")

    def set_status(self, status: str, terminal: bool = False) -> None:
        self.status_label.setText(status)
        if status == "已完成":
            color = "#1EBE56"
        elif status == "已取消" or status == "執行失敗":
            color = "#dd2929"
        else:
            color = "#3998d8"
        self.status_dot.set_color(color)
        self.terminal = terminal
        self.dismiss_button.setEnabled(True)
        self.dismiss_button.setToolTip(
            "移除這則已結束的通知" if terminal else "隱藏這個 Session"
        )

    def set_turn_id(self, turn_id: str) -> None:
        self.turn_id = turn_id
        self._update_tooltip()

    def set_title(self, title: str) -> None:
        self.title = title
        self._update_visible_title()
        self._update_tooltip()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.name_label and event.type() == QEvent.Type.Resize:
            self._update_visible_title()
        return super().eventFilter(watched, event)

    def _update_visible_title(self) -> None:
        source = self.title or f"Session {self.number}"
        directory, separator, _ = source.partition(" > ")
        self.name_label.set_directory_prefix(directory if separator else "")
        visible_title = source[:MAX_TITLE_CHARS]
        shortened = len(source) > MAX_TITLE_CHARS
        while visible_title and self.name_label.display_width(
            visible_title + ("..." if shortened else "")
        ) > self.name_label.width():
            visible_title = visible_title[:-1]
            shortened = True
        display = visible_title + ("..." if shortened else "")
        if self.name_label.text() != display:
            self.name_label.setText(display)

    def _update_tooltip(self) -> None:
        self.setToolTip(
            f"Session: {self.session_id or '未提供'}\n"
            f"Turn: {self.turn_id or '未提供'}"
            + (f"\n標題: {self.title}" if self.title else "")
        )


class WidthResizeHandle(QWidget):
    def __init__(self, panel: TurnPanel, edge: str):
        super().__init__(panel)
        self.panel = panel
        self.edge = edge
        self.start_x: int | None = None
        self.start_geometry = QRect()
        self.setCursor(Qt.CursorShape.SizeHorCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_x = event.globalPosition().toPoint().x()
            self.start_geometry = self.panel.geometry()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.start_x is None or not event.buttons() & Qt.MouseButton.LeftButton:
            return
        delta = event.globalPosition().toPoint().x() - self.start_x
        area = (QApplication.screenAt(self.start_geometry.center()) or QApplication.primaryScreen())
        if area is None:
            return
        bounds = area.availableGeometry()
        maximum = min(
            MAX_PANEL_WIDTH,
            bounds.right() - self.start_geometry.left() + 1
            if self.edge == "right" else self.start_geometry.right() - bounds.left() + 1,
        )
        maximum = max(MIN_PANEL_WIDTH, maximum)
        width = max(
            min(MIN_PANEL_WIDTH, maximum),
            min(maximum, self.start_geometry.width() + delta * (1 if self.edge == "right" else -1)),
        )
        x = self.start_geometry.left() if self.edge == "right" else self.start_geometry.right() - width + 1
        self.panel.setGeometry(x, self.start_geometry.top(), width, self.start_geometry.height())
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.start_x is not None:
            self.start_x = None
            if self.panel.width() != self.start_geometry.width():
                self.panel.width_changed.emit(self.panel.width())
            event.accept()


class TurnPanel(QWidget):
    width_changed = Signal(int)
    session_hidden_changed = Signal(str, bool)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(MIN_PANEL_WIDTH)
        self.setMaximumWidth(MAX_PANEL_WIDTH)
        self.rows: dict[str, SessionRow] = {}
        self.session_numbers: dict[str, int] = {}
        self.session_titles: dict[str, str] = {}
        self.session_states: dict[str, tuple[str, str, bool]] = {}
        self.hidden_sessions: set[str] = set()
        self.next_number = 1

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        card = QFrame()
        card.setObjectName("turnCard")
        outer.addWidget(card)
        content = QVBoxLayout(card)
        content.setContentsMargins(10, 10, 10, 10)
        content.setSpacing(6)
        heading = QLabel("SESSION 工作狀態")
        self.heading = heading
        heading.setObjectName("turnHeading")
        content.addWidget(heading)
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("turnScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.viewport().setObjectName("turnViewport")
        self.list_widget = QWidget()
        self.list_widget.setObjectName("turnList")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(4)
        self.empty_label = QLabel("閒置中")
        self.empty_label.setObjectName("emptyTurns")
        self.list_layout.addWidget(self.empty_label)
        self.list_layout.addStretch()
        self.scroll_area.setWidget(self.list_widget)
        content.addWidget(self.scroll_area)
        self.setStyleSheet("""
            QFrame#turnCard { background: #ffffff; border: 1px solid #dbe5ee; border-radius: 14px; }
            QFrame#sessionRow { background: #f3f7fa; border: 1px solid #e0e9f0; border-radius: 9px; }
            QLabel { background: transparent; border: none; color: #172b3d;
                     font-family: "Noto Sans TC", "Microsoft JhengHei", "Segoe UI"; }
            QLabel#turnHeading { color: #52687d; font-size: 12px; font-weight: 700; }
            QLabel#sessionName { color: #5f6368; font-size: 11px; }
            QLabel#turnStatus { color: #111111; font-size: 12px; font-weight: 700; }
            QLabel#emptyTurns { color: #8091a0; font-size: 12px; }
            QScrollArea#turnScroll { background: #ffffff; border: none; }
            QWidget#turnViewport, QWidget#turnList { background: #ffffff; }
        """)
        self.left_resize_handle = WidthResizeHandle(self, "left")
        self.right_resize_handle = WidthResizeHandle(self, "right")
        self.set_panel_width(DEFAULT_PANEL_WIDTH)
        self._resize_for_rows()

    def set_panel_width(self, width: int) -> None:
        screen = QApplication.primaryScreen()
        maximum = min(MAX_PANEL_WIDTH, screen.availableGeometry().width()) if screen else MAX_PANEL_WIDTH
        self.resize(max(MIN_PANEL_WIDTH, min(maximum, width)), self.height())

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.left_resize_handle.setGeometry(0, 0, 8, self.height())
        self.right_resize_handle.setGeometry(self.width() - 8, 0, 8, self.height())
        self.left_resize_handle.raise_()
        self.right_resize_handle.raise_()

    def set_turn(
        self, key: tuple[str, str], status: str, terminal: bool = False, title: str = ""
    ) -> None:
        session_id, turn_id = key
        normalized_title = " ".join(title.split())
        if normalized_title:
            self.session_titles[session_id] = normalized_title
        self.session_states[session_id] = (turn_id, status, terminal)
        if session_id in self.hidden_sessions:
            return
        row = self.rows.get(session_id)
        if row is None:
            if session_id not in self.session_numbers:
                self.session_numbers[session_id] = self.next_number
                self.next_number += 1
            row = SessionRow(session_id, self.session_numbers[session_id])
            row.dismiss_requested.connect(self.dismiss_session)
            self.rows[session_id] = row
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)
        if session_id in self.session_titles:
            row.set_title(self.session_titles[session_id])
        row.set_turn_id(turn_id)
        row.set_status(status, terminal)
        self.empty_label.setVisible(not self.rows)
        self._resize_for_rows()

    def dismiss_session(self, session_id: str) -> None:
        row = self.rows.get(session_id)
        if row is None:
            return
        if not row.terminal:
            self.hidden_sessions.add(session_id)
        del self.rows[session_id]
        self.list_layout.removeWidget(row)
        row.deleteLater()
        self.empty_label.setVisible(not self.rows)
        self._resize_for_rows()
        if session_id in self.hidden_sessions:
            self.session_hidden_changed.emit(session_id, True)

    def restore_session(self, session_id: str) -> None:
        if session_id not in self.hidden_sessions:
            return
        self.hidden_sessions.remove(session_id)
        state = self.session_states.get(session_id)
        if state is not None:
            turn_id, status, terminal = state
            self.set_turn(
                (session_id, turn_id),
                status,
                terminal,
                self.session_titles.get(session_id, ""),
            )
        self.session_hidden_changed.emit(session_id, False)

    def hidden_session_items(self) -> list[tuple[str, str]]:
        def sort_key(session_id: str) -> int:
            return self.session_numbers.get(session_id, 0)

        return [
            (
                session_id,
                self.session_titles.get(session_id)
                or f"Session {self.session_numbers.get(session_id, '?')}",
            )
            for session_id in sorted(self.hidden_sessions, key=sort_key)
        ]

    def end_session(self, session_id: str) -> None:
        state = self.session_states.get(session_id)
        if state is not None:
            turn_id, _, _ = state
            self.session_states[session_id] = (turn_id, "已結束", True)
        row = self.rows.get(session_id)
        if row is not None and not row.terminal:
            row.set_status("已結束", True)
        self._resize_for_rows()

    def _resize_for_rows(self) -> None:
        count = max(1, len(self.rows))
        self.setFixedHeight(
            PANEL_HEIGHT_BASE + min(count, MAX_VISIBLE_ROWS) * PANEL_ROW_HEIGHT
        )
