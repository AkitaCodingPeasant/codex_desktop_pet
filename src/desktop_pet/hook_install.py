"""Install or update this app's Codex hooks without replacing unrelated hooks."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


BRIDGE = Path(__file__).resolve().with_name("hook_bridge.py")
EVENTS = (
    "UserPromptSubmit", "PreToolUse", "PermissionRequest", "PostToolUse",
    "Stop", "Interrupt", "SessionEnd",
)


def target_path() -> Path:
    home = os.environ.get("CODEX_HOME")
    return (Path(home).expanduser() if home else Path.home() / ".codex") / "hooks.json"


def build_hooks(python: Path | None = None, bridge: Path = BRIDGE) -> dict:
    python = python or Path(sys.executable)
    if not python.is_file() or not bridge.is_file():
        raise FileNotFoundError("找不到 Python 或 hook_bridge.py，無法設定 Hook。")
    command = f'"{python}" "{bridge}"'
    windows_command = f'& "{python}" "{bridge}"'
    return {
        event: [{"hooks": [{
            "type": "command", "command": command,
            "commandWindows": windows_command, "timeout": 3,
        }]}]
        for event in EVENTS
    }


def _is_pet_handler(handler: object) -> bool:
    if not isinstance(handler, dict) or handler.get("type") != "command":
        return False
    commands = (handler.get("command"), handler.get("commandWindows"))
    return any(
        isinstance(command, str)
        and "hook_bridge.py" in command.lower()
        and ("desktop_pet" in command.lower() or "desktop-pet" in command.lower())
        for command in commands
    )


def merge_hooks(data: dict, source: dict) -> bool:
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("hooks.json 的 hooks 欄位不是物件。")
    changed = False
    for event, groups in source.items():
        existing = hooks.setdefault(event, [])
        if not isinstance(existing, list):
            raise ValueError(f"hooks.json 的 {event} 欄位不是清單。")
        new_group = groups[0]
        for group in existing[:]:
            if group == new_group:
                continue
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                continue
            remaining = [h for h in group["hooks"] if not _is_pet_handler(h)]
            if len(remaining) == len(group["hooks"]):
                continue
            if not remaining:
                existing.remove(group)
            else:
                group["hooks"] = remaining
            changed = True
        if new_group not in existing:
            existing.append(new_group)
            changed = True
    return changed


def install_hooks(target: Path | None = None, python: Path | None = None) -> tuple[Path, bool]:
    target = target or target_path()
    source = build_hooks(python)
    if target.exists():
        data = json.loads(target.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("hooks.json 的根目錄不是物件。")
    else:
        data = {"hooks": {}}
    changed = merge_hooks(data, source)
    if not changed:
        return target, False

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.copy2(target, target.with_name("hooks.json.bak.desktop_pet_v2"))
    temporary = target.with_name("hooks.json.tmp.desktop_pet_v2")
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target, True
