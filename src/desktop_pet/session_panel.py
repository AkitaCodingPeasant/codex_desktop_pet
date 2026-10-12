from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
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
    "tool.started": "工作中",
    "action_required": "等待授權",
    "user_input_requested": "等待回覆",
    "user_input_completed": "思考中",
    **TERMINAL_STATUSES,
}


class SessionRow(QFrame):
    dismiss_requested = Signal(object)

    def __init__(self, session_id: str, number: int):
        super().__init__()
        self.session_id = session_id
        self.terminal = False
        self.setObjectName("sessionRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 8, 8)
        layout.setSpacing(8)
        self.name_label = QLabel(f"Session {number}")
        self.name_label.setObjectName("sessionName")
        self.status_label = QLabel("思考中")
        self.status_label.setObjectName("turnStatus")
        self.dismiss_button = QPushButton("×")
        self.dismiss_button.setObjectName("dismissSession")
        self.dismiss_button.setToolTip("移除這則已結束的通知")
        self.dismiss_button.setFixedSize(24, 24)
        self.dismiss_button.setEnabled(False)
        self.dismiss_button.clicked.connect(lambda: self.dismiss_requested.emit(self.session_id))
        layout.addWidget(self.name_label)
        layout.addStretch()
        layout.addWidget(self.status_label)
        layout.addWidget(self.dismiss_button)

    def set_status(self, status: str, terminal: bool = False) -> None:
        self.status_label.setText(status)
        self.terminal = terminal
        self.dismiss_button.setEnabled(terminal)

    def set_turn_id(self, turn_id: str) -> None:
        self.setToolTip(
            f"Session: {self.session_id or '未提供'}\nTurn: {turn_id or '未提供'}"
        )


class TurnPanel(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(254)
        self.rows: dict[str, SessionRow] = {}
        self.session_numbers: dict[str, int] = {}
        self.next_number = 1

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        card = QFrame()
        card.setObjectName("turnCard")
        outer.addWidget(card)
        content = QVBoxLayout(card)
        content.setContentsMargins(12, 12, 12, 12)
        content.setSpacing(8)
        heading = QLabel("SESSION 工作狀態")
        self.heading = heading
        heading.setObjectName("turnHeading")
        content.addWidget(heading)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("turnScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(6)
        self.empty_label = QLabel("目前沒有 session")
        self.empty_label.setObjectName("emptyTurns")
        self.list_layout.addWidget(self.empty_label)
        self.list_layout.addStretch()
        self.scroll.setWidget(self.list_widget)
        content.addWidget(self.scroll)
        self.setStyleSheet("""
            QFrame#turnCard { background: #ffffff; border: 1px solid #dbe5ee; border-radius: 14px; }
            QFrame#sessionRow { background: #f3f7fa; border: 1px solid #e0e9f0; border-radius: 9px; }
            QLabel { background: transparent; border: none; color: #172b3d;
                     font-family: "Noto Sans TC", "Microsoft JhengHei", "Segoe UI"; }
            QLabel#turnHeading { color: #52687d; font-size: 12px; font-weight: 700; }
            QLabel#sessionName { font-size: 12px; font-weight: 700; }
            QLabel#turnStatus { font-size: 12px; }
            QLabel#emptyTurns { color: #8091a0; font-size: 12px; }
            QScrollArea#turnScroll { background: transparent; border: none; }
            QPushButton#dismissSession { border: none; border-radius: 12px; color: #52687d;
                                     background: #e3ebf1; font-size: 17px; }
            QPushButton#dismissSession:hover { background: #d2e0e9; }
            QPushButton#dismissSession:disabled { color: #b8c3cc; background: transparent; }
        """)
        self._resize_for_rows()

    def set_turn(self, key: tuple[str, str], status: str, terminal: bool = False) -> None:
        session_id, turn_id = key
        row = self.rows.get(session_id)
        if row is None:
            if session_id not in self.session_numbers:
                self.session_numbers[session_id] = self.next_number
                self.next_number += 1
            row = SessionRow(session_id, self.session_numbers[session_id])
            row.dismiss_requested.connect(self.dismiss_session)
            self.rows[session_id] = row
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)
        row.set_turn_id(turn_id)
        row.set_status(status, terminal)
        self.empty_label.setVisible(not self.rows)
        self._resize_for_rows()

    def dismiss_session(self, session_id: str) -> None:
        row = self.rows.get(session_id)
        if row is None or not row.terminal:
            return
        del self.rows[session_id]
        self.list_layout.removeWidget(row)
        row.deleteLater()
        self.empty_label.setVisible(not self.rows)
        self._resize_for_rows()

    def end_session(self, session_id: str) -> None:
        row = self.rows.get(session_id)
        if row is not None and not row.terminal:
            row.set_status("已結束", True)
        self._resize_for_rows()

    def _resize_for_rows(self) -> None:
        count = max(1, len(self.rows))
        self.setFixedHeight(58 + min(count, 7) * 46)
