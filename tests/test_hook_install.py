from __future__ import annotations

import json
import unittest

import install_codex_hooks


class HookInstallTests(unittest.TestCase):
    def test_existing_question_hook_is_upgraded_to_all_tools(self) -> None:
        source = json.loads(
            install_codex_hooks.SOURCE.read_text(encoding="utf-8")
        )["hooks"]
        new_group = source["PreToolUse"][0]
        old_group = {
            "matcher": "request_user_input(_async)?$",
            "hooks": new_group["hooks"],
        }
        data = {"hooks": {"PreToolUse": [old_group]}}
        self.assertTrue(install_codex_hooks.merge_hooks(data, source))
        self.assertEqual(data["hooks"]["PreToolUse"], [new_group])
        self.assertFalse(install_codex_hooks.merge_hooks(data, source))


if __name__ == "__main__":
    unittest.main()
