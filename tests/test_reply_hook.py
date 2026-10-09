from __future__ import annotations

import json
import io
import socket
import unittest
from unittest.mock import patch

from desktop_pet.hook_bridge import CODEX_EVENTS, HOST, MAX_REPLY_CHARS, completion_preview, event_for_hook, reply_preview, send_event
from desktop_pet.hook_listener import HookListener


class ReplyHookTests(unittest.TestCase):
    def test_prompt_and_tool_events_have_distinct_meanings(self) -> None:
        self.assertEqual(CODEX_EVENTS["UserPromptSubmit"], "turn.started")
        self.assertEqual(CODEX_EVENTS["PostToolUse"], "turn.in_progress")
        self.assertEqual(CODEX_EVENTS["SessionEnd"], "session.ended")

    def test_user_input_tool_switches_to_asking(self) -> None:
        for tool_name in ("request_user_input", "functions.request_user_input_async"):
            self.assertEqual(
                event_for_hook({"hook_event_name": "PreToolUse", "tool_name": tool_name}),
                "user_input_requested",
            )
        self.assertEqual(
            event_for_hook({"hook_event_name": "PreToolUse", "tool_name": "Bash"}),
            "tool.started",
        )
        self.assertIsNone(event_for_hook({"hook_event_name": "PostToolUse", "tool_name": "request_user_input_async"}))
        self.assertEqual(
            event_for_hook({"hook_event_name": "PostToolUse", "tool_name": "request_user_input"}),
            "user_input_completed",
        )

    def test_pretooluse_hook_sends_question_event(self) -> None:
        from desktop_pet.hook_bridge import main
        import desktop_pet.hook_bridge as bridge

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind((HOST, 0))
            receiver.settimeout(2)
            hook_input = json.dumps({
                "hook_event_name": "PreToolUse",
                "tool_name": "request_user_input_async",
                "session_id": "session-a",
                "turn_id": "turn-a",
            }).encode("utf-8")
            with (
                patch.object(bridge, "PORT", receiver.getsockname()[1]),
                patch("sys.argv", ["hook_bridge.py"]),
                patch("sys.stdin", io.TextIOWrapper(io.BytesIO(hook_input), encoding="utf-8")),
            ):
                main()
            packet, _ = receiver.recvfrom(4096)
        self.assertEqual(json.loads(packet.decode("utf-8")), {
            "event": "user_input_requested",
            "message": "",
            "session_id": "session-a",
            "turn_id": "turn-a",
        })

    def test_pretooluse_hook_sends_working_event(self) -> None:
        from desktop_pet.hook_bridge import main
        import desktop_pet.hook_bridge as bridge

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind((HOST, 0))
            receiver.settimeout(2)
            hook_input = json.dumps({
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": "session-a",
                "turn_id": "turn-a",
            }).encode("utf-8")
            with (
                patch.object(bridge, "PORT", receiver.getsockname()[1]),
                patch("sys.argv", ["hook_bridge.py"]),
                patch("sys.stdin", io.TextIOWrapper(io.BytesIO(hook_input), encoding="utf-8")),
            ):
                main()
            packet, _ = receiver.recvfrom(4096)
        self.assertEqual(json.loads(packet.decode("utf-8"))["event"], "tool.started")

    def test_stop_hook_sends_first_100_characters(self) -> None:
        from desktop_pet.hook_bridge import main

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind((HOST, 0))
            receiver.settimeout(2)
            import desktop_pet.hook_bridge as bridge

            original_port = bridge.PORT
            bridge.PORT = receiver.getsockname()[1]
            try:
                hook_input = json.dumps({
                    "hook_event_name": "Stop",
                    "session_id": "session-a",
                    "turn_id": "turn-a",
                    "last_assistant_message": "\n這是一段測試回覆 🐾\n" * 20,
                }, ensure_ascii=False)
                raw_input = io.TextIOWrapper(io.BytesIO(hook_input.encode("utf-8")), encoding="cp950")
                with self.assertRaises(UnicodeDecodeError):
                    json.load(raw_input)
                raw_input.seek(0)
                with patch("sys.argv", ["hook_bridge.py"]), patch("sys.stdin", raw_input):
                    main()
                packet, _ = receiver.recvfrom(4096)
            finally:
                bridge.PORT = original_port
        payload = json.loads(packet.decode("utf-8"))
        self.assertEqual(payload["event"], "turn.completed")
        self.assertEqual((payload["session_id"], payload["turn_id"]), ("session-a", "turn-a"))
        self.assertEqual(payload["message"], ("這是一段測試回覆 🐾 " * 20).strip()[:MAX_REPLY_CHARS] + "...")

    def test_reply_preview_removes_markdown_before_counting(self) -> None:
        message = "# 標題\n\n- **粗體**與*斜體*、~~刪除線~~\n- [連結](https://example.com)與`程式碼`\n"
        self.assertEqual(reply_preview(message), "標題 粗體與斜體、刪除線 連結與程式碼")
        self.assertEqual(reply_preview("> 引述\n\n```python\nprint(1)\n```"), "引述 print(1)")
        self.assertEqual(reply_preview("![圖片說明](https://example.com/a.png)"), "圖片說明")
        self.assertEqual(reply_preview("**" + "甲" * 100 + "**"), "甲" * 100)
        self.assertEqual(reply_preview("**" + "甲" * 101 + "**"), "甲" * 100 + "...")

    def test_completion_keeps_change_totals_after_truncated_reply(self) -> None:
        message = "甲" * 120 + "\n\n更動 3 個檔案，新增 18 行，刪除 5 行。"
        self.assertEqual(
            completion_preview(message),
            "甲" * 100 + "...\n已變更 3 個檔案 +18 -5",
        )
        self.assertEqual(
            completion_preview("更動檔案數：2；新增行數：7；刪減行數：1"),
            "已變更 2 個檔案 +7 -1",
        )
        self.assertEqual(
            completion_preview("測試回覆\n變更 1 個檔案 +1 -1"),
            "測試回覆\n已變更 1 個檔案 +1 -1",
        )
        self.assertEqual(
            completion_preview("已變更 1 個檔案 +1 -1"),
            "已變更 1 個檔案 +1 -1",
        )
        self.assertEqual(completion_preview("已完成，沒有檔案變更。"), "已完成，沒有檔案變更。")

    def test_listener_receives_message(self) -> None:
        from PySide6.QtCore import QCoreApplication
        import desktop_pet.hook_bridge as bridge
        import desktop_pet.hook_listener as listener_module

        app = QCoreApplication.instance() or QCoreApplication([])
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as temporary:
            temporary.bind((HOST, 0))
            port = temporary.getsockname()[1]
        with patch.object(bridge, "PORT", port), patch.object(listener_module, "PORT", port):
            listener = HookListener()
            events: list[tuple[str, str, str, str]] = []
            listener.event_received.connect(
                lambda event, message, session, turn: events.append((event, message, session, turn))
            )
            try:
                send_event("turn.completed", "**回覆內容**", "session-a", "turn-a")
                listener._receive_pending()
                self.assertEqual(events, [("turn.completed", "回覆內容", "session-a", "turn-a")])
                send_event(
                    "turn.completed",
                    "甲" * 120 + "\n更動 3 個檔案，新增 18 行，刪除 5 行",
                    "session-a",
                    "turn-b",
                )
                listener._receive_pending()
                self.assertEqual(
                    events[-1][1],
                    "甲" * 100 + "...\n已變更 3 個檔案 +18 -5",
                )
            finally:
                listener.close()
        self.assertIsNotNone(app)



if __name__ == "__main__":
    unittest.main()
