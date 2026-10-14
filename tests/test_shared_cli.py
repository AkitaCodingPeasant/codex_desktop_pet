from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
import pet_hook  # noqa: E402

from desktop_pet import cli_path  # noqa: E402


class SharedCliTests(unittest.TestCase):
    def test_no_arguments_prints_help_without_error(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(pet_hook.main([]), 0)
        self.assertIn("usage: pet-hook", output.getvalue())
        self.assertIn("turn.started", output.getvalue())
        self.assertIn("--session-id", output.getvalue())
        self.assertIn("--status", output.getvalue())
        self.assertIn("--subtitle", output.getvalue())
        self.assertIn("範例（CMD）：", output.getvalue())
        self.assertIn("pet-hook tool.started", output.getvalue())
        self.assertIn("pet-hook turn.completed", output.getvalue())

    def test_cli_sends_separate_title_and_message(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind((pet_hook.HOST, 0))
            receiver.settimeout(2)
            with patch.object(pet_hook, "PORT", receiver.getsockname()[1]):
                self.assertEqual(pet_hook.main([
                    "turn.started", "--title", "MyTool", "--message", "正在產生影片",
                    "--status", "排程中",
                    "--session-id", "mytool:project-123", "--turn-id", "job-456",
                ]), 0)
            packet, _ = receiver.recvfrom(4096)
        self.assertEqual(json.loads(packet.decode("utf-8")), {
            "event": "turn.started",
            "title": "MyTool",
            "subtitle": "",
            "message": "正在產生影片",
            "status": "排程中",
            "session_id": "mytool:project-123",
            "turn_id": "job-456",
        })

    def test_cli_sends_subtitle(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind((pet_hook.HOST, 0))
            receiver.settimeout(2)
            with patch.object(pet_hook, "PORT", receiver.getsockname()[1]):
                self.assertEqual(pet_hook.main([
                    "tool.started", "--title", "MyTool", "--subtitle", "專案 A",
                    "--session-id", "mytool:project-123", "--turn-id", "job-456",
                ]), 0)
            packet, _ = receiver.recvfrom(4096)
        payload = json.loads(packet.decode("utf-8"))
        self.assertEqual(payload["title"], "MyTool")
        self.assertEqual(payload["subtitle"], "專案 A")

    def test_cli_requires_turn_id_except_for_session_end(self) -> None:
        with self.assertRaises(SystemExit) as error:
            pet_hook.main(["turn.started", "--session-id", "mytool:project-123"])
        self.assertEqual(error.exception.code, 2)

    def test_user_path_installer_preserves_existing_value_and_is_idempotent(self) -> None:
        registry_key = MagicMock()
        registry_key.__enter__.return_value = registry_key
        existing = r"C:\Tools;%USERPROFILE%\Scripts"
        with (
            patch.object(cli_path.winreg, "CreateKeyEx", return_value=registry_key),
            patch.object(
                cli_path.winreg, "QueryValueEx",
                side_effect=[
                    (existing, cli_path.winreg.REG_EXPAND_SZ),
                    (existing + ";" + str(cli_path.CLI_DIRECTORY), cli_path.winreg.REG_EXPAND_SZ),
                ],
            ),
            patch.object(cli_path.winreg, "SetValueEx") as set_value,
            patch.object(cli_path, "_notify_environment_changed") as notify,
            patch.dict(os.environ, {"PATH": existing}),
        ):
            self.assertTrue(cli_path.add_cli_to_user_path())
            self.assertFalse(cli_path.add_cli_to_user_path())
            self.assertTrue(cli_path._contains_directory(
                os.environ["PATH"], cli_path.CLI_DIRECTORY
            ))
        set_value.assert_called_once_with(
            registry_key, "Path", 0, cli_path.winreg.REG_EXPAND_SZ,
            existing + ";" + str(cli_path.CLI_DIRECTORY),
        )
        notify.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
