"""Merge this pet's hooks into the user's existing Codex hooks.json."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "codex_hooks.template.json"
TARGET = Path.home() / ".codex" / "hooks.json"


def merge_hooks(data: dict, source: dict) -> bool:
    hooks = data.setdefault("hooks", {})

    changed = False
    for event_name, groups in source.items():
        existing = hooks.setdefault(event_name, [])
        for group in groups:
            if event_name == "PreToolUse":
                old_groups = [
                    item for item in existing
                    if item.get("matcher") == "request_user_input(_async)?$"
                    and item.get("hooks") == group["hooks"]
                ]
                for old_group in old_groups:
                    existing.remove(old_group)
                    changed = True
            if group not in existing:
                existing.append(group)
                changed = True

    return changed


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))["hooks"]
    if TARGET.exists():
        data = json.loads(TARGET.read_text(encoding="utf-8"))
    else:
        data = {"hooks": {}}

    changed = merge_hooks(data, source)

    if not changed:
        print("Codex hooks are already installed.")
        return

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if TARGET.exists():
        shutil.copy2(TARGET, TARGET.with_name("hooks.json.bak.desktop_pet_v2"))
    temporary = TARGET.with_name("hooks.json.tmp.desktop_pet_v2")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(TARGET)
    print(f"Installed desktop pet hooks in {TARGET}")


if __name__ == "__main__":
    main()
