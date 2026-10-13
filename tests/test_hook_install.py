from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from desktop_pet.hook_install import (
    CLAUDE_EVENTS, build_claude_hooks, build_hooks, claude_target_path,
    install_claude_hooks, install_hooks, merge_hooks, target_path,
)


class HookInstallTests(unittest.TestCase):
    def test_old_hook_is_updated_without_removing_other_handlers(self) -> None:
        source = build_hooks()
        current = source["PreToolUse"][0]["hooks"][0]
        self.assertIn("hook_bridge.py", current["command"])
        self.assertIn("& ", current["commandWindows"])
        old = {
            "type": "command",
            "command": 'call "D:\\desktop_pet_v2\\.venv\\Scripts\\python.exe" "D:\\desktop_pet_v2\\src\\desktop_pet\\hook_bridge.py"',
        }
        other = {"type": "command", "command": "echo keep-me"}
        data = {"hooks": {"PreToolUse": [
            {"matcher": "request_user_input(_async)?$", "hooks": [old, other]},
        ]}}
        self.assertTrue(merge_hooks(data, source))
        groups = data["hooks"]["PreToolUse"]
        self.assertEqual(groups[0]["hooks"], [other])
        self.assertEqual(groups[1], source["PreToolUse"][0])
        self.assertFalse(merge_hooks(data, source))

    def test_install_preserves_other_hooks_and_backs_up_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "hooks.json"
            original = {"description": "Mine", "hooks": {"Stop": [
                {"hooks": [{"type": "command", "command": "echo mine"}]}
            ]}}
            target.write_text(json.dumps(original), encoding="utf-8")
            self.assertEqual(install_hooks(target), (target, True))
            installed = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(installed["hooks"]["Stop"][0], original["hooks"]["Stop"][0])
            backup = target.with_name("hooks.json.bak.desktop_pet_v2")
            self.assertEqual(json.loads(backup.read_text(encoding="utf-8")), original)
            self.assertEqual(install_hooks(target), (target, False))
            self.assertEqual(json.loads(backup.read_text(encoding="utf-8")), original)

    def test_codex_home_is_used_when_set(self) -> None:
        with patch.dict("os.environ", {"CODEX_HOME": "D:/custom-codex"}):
            self.assertEqual(target_path(), Path("D:/custom-codex/hooks.json"))


    def test_claude_install_keeps_other_settings_and_hooks(self) -> None:
        source = build_claude_hooks()
        self.assertEqual(set(source), set(CLAUDE_EVENTS))
        command = source["Stop"][0]["hooks"][0]["command"]
        self.assertTrue(command.endswith("--source claude"))
        self.assertNotIn("\\", command)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "settings.json"
            original = {"model": "opus", "hooks": {"Stop": [
                {"hooks": [{"type": "command", "command": "echo mine"}]}
            ]}}
            target.write_text(json.dumps(original), encoding="utf-8")
            self.assertEqual(install_claude_hooks(target), (target, True))
            installed = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(installed["model"], "opus")
            self.assertEqual(installed["hooks"]["Stop"][0], original["hooks"]["Stop"][0])
            self.assertEqual(installed["hooks"]["Stop"][1], source["Stop"][0])
            backup = target.with_name("settings.json.bak.desktop_pet")
            self.assertEqual(json.loads(backup.read_text(encoding="utf-8")), original)
            self.assertEqual(install_claude_hooks(target), (target, False))

    def test_claude_config_dir_is_used_when_set(self) -> None:
        with patch.dict("os.environ", {"CLAUDE_CONFIG_DIR": "D:/custom-claude"}):
            self.assertEqual(claude_target_path(), Path("D:/custom-claude/settings.json"))


if __name__ == "__main__":
    unittest.main()
