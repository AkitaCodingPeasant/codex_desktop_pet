from __future__ import annotations

import json
import socket

from PySide6.QtCore import QObject, QTimer, Signal

from desktop_pet.hook_bridge import HOST, PET_EVENTS, PORT


class HookListener(QObject):
    event_received = Signal(str, str, str, str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((HOST, PORT))
        self.socket.setblocking(False)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._receive_pending)
        self.timer.start(50)

    def _receive_pending(self) -> None:
        while True:
            try:
                packet, _ = self.socket.recvfrom(4096)
            except BlockingIOError:
                return
            try:
                payload = json.loads(packet.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            event_name = payload.get("event")
            message = payload.get("message", "")
            session_id = payload.get("session_id", "")
            turn_id = payload.get("turn_id", "")
            if event_name in PET_EVENTS:
                self.event_received.emit(
                    event_name,
                    message if isinstance(message, str) else "",
                    session_id if isinstance(session_id, str) else "",
                    turn_id if isinstance(turn_id, str) else "",
                )

    def close(self) -> None:
        self.timer.stop()
        self.socket.close()
