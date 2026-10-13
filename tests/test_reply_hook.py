from __future__ import annotations

import io
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from desktop_pet.hook_bridge import CODEX_EVENTS, HOST, MAX_REPLY_CHARS, MAX_SESSION_TITLE_CHARS, completion_preview, event_for_hook, reply_preview, send_event, should_ignore_hook, working_directory_title
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
            "title": "",
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

    def test_memory_writing_agent_session_is_ignored_until_session_end(self) -> None:
        import desktop_pet.hook_bridge as bridge

        with tempfile.TemporaryDirectory() as directory, patch.object(
            bridge, "IGNORED_SESSION_DIR", Path(directory)
        ):
            self.assertTrue(should_ignore_hook({
                "hook_event_name": "UserPromptSubmit",
                "session_id": "memory-session",
                "prompt": "## Memory Writing Agent: Phase 2 (Consolidation)\n\n工作內容",
            }))
            self.assertTrue(should_ignore_hook({
                "hook_event_name": "PreToolUse",
                "session_id": "memory-session",
                "tool_name": "Bash",
            }))
            self.assertTrue(should_ignore_hook({
                "hook_event_name": "Stop",
                "session_id": "memory-session",
            }))
            self.assertTrue(should_ignore_hook({
                "hook_event_name": "SessionEnd",
                "session_id": "memory-session",
            }))
            self.assertFalse(should_ignore_hook({
                "hook_event_name": "PreToolUse",
                "session_id": "memory-session",
                "tool_name": "Bash",
            }))

    def test_memory_writing_agent_hook_does_not_send_pet_event(self) -> None:
        import desktop_pet.hook_bridge as bridge

        hook_input = json.dumps({
            "hook_event_name": "UserPromptSubmit",
            "session_id": "memory-session",
            "turn_id": "memory-turn",
            "prompt": "## Memory Writing Agent: Phase 2 (Consolidation)",
        }).encode("utf-8")
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(bridge, "IGNORED_SESSION_DIR", Path(directory)),
            patch.object(bridge, "send_event") as send_event_mock,
            patch("sys.argv", ["hook_bridge.py"]),
            patch("sys.stdin", io.TextIOWrapper(io.BytesIO(hook_input), encoding="utf-8")),
        ):
            bridge.main()
        send_event_mock.assert_not_called()

    def test_regular_prompt_that_mentions_memory_writer_is_not_ignored(self) -> None:
        import desktop_pet.hook_bridge as bridge

        with tempfile.TemporaryDirectory() as directory, patch.object(
            bridge, "IGNORED_SESSION_DIR", Path(directory)
        ):
            self.assertFalse(should_ignore_hook({
                "hook_event_name": "UserPromptSubmit",
                "session_id": "regular-session",
                "prompt": "請說明 Memory Writing Agent 是什麼",
            }))

    def test_user_prompt_hook_sends_short_session_title(self) -> None:
        from desktop_pet.hook_bridge import main
        import desktop_pet.hook_bridge as bridge

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind((HOST, 0))
            receiver.settimeout(2)
            hook_input = json.dumps({
                "hook_event_name": "UserPromptSubmit",
                "session_id": "session-a",
                "turn_id": "turn-1",
                "cwd": r"D:\codex_desktop_pet",
                "prompt": "  幫我寫一個\n桌寵狀態面板，再加入來源辨識功能  ",
            }, ensure_ascii=False).encode("utf-8")
            with (
                patch.object(bridge, "PORT", receiver.getsockname()[1]),
                patch("sys.argv", ["hook_bridge.py"]),
                patch("sys.stdin", io.TextIOWrapper(io.BytesIO(hook_input), encoding="utf-8")),
            ):
                main()
            packet, _ = receiver.recvfrom(4096)
        payload = json.loads(packet.decode("utf-8"))
        self.assertEqual(payload["event"], "turn.started")
        self.assertEqual(payload["title"], "codex_desktop_pet")
        self.assertEqual(payload["message"], "幫我寫一個 桌寵狀態面板，再加入來源辨識功能")

    def test_working_directory_title_uses_leaf_directory(self) -> None:
        self.assertEqual(
            working_directory_title("C:\\Project\\codex_desktop_pet\\"),
            "codex_desktop_pet",
        )
        self.assertEqual(working_directory_title(""), "")

    def test_long_session_title_preview_has_three_dots(self) -> None:
        from desktop_pet.hook_bridge import session_title_preview

        self.assertEqual(
            session_title_preview("A" * MAX_SESSION_TITLE_CHARS),
            "A" * MAX_SESSION_TITLE_CHARS,
        )
        self.assertEqual(
            session_title_preview("A" * (MAX_SESSION_TITLE_CHARS + 1)),
            "A" * MAX_SESSION_TITLE_CHARS + "...",
        )

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
            events: list[tuple[str, str, str, str, str, str]] = []
            listener.event_received.connect(
                lambda event, message, session, turn, title, status: events.append(
                    (event, message, session, turn, title, status)
                )
            )
            try:
                send_event(
                    "turn.completed", "**回覆內容**", "session-a", "turn-a", "MyTool"
                )
                listener._receive_pending()
                self.assertEqual(
                    events,
                    [("turn.completed", "回覆內容", "session-a", "turn-a", "MyTool", "")],
                )
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
                legacy_packet = json.dumps({
                    "event": "turn.started",
                    "message": "舊版訊息",
                    "status": "排程中",
                    "session_id": "legacy-session",
                    "turn_id": "legacy-turn",
                }, ensure_ascii=False).encode("utf-8")
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                    sender.sendto(legacy_packet, (HOST, port))
                listener._receive_pending()
                self.assertEqual(
                    events[-1],
                    ("turn.started", "舊版訊息", "legacy-session", "legacy-turn", "", "排程中"),
                )
            finally:
                listener.close()
        self.assertIsNotNone(app)



if __name__ == "__main__":
    unittest.main()
