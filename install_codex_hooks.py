"""Command-line entry point for installing the desktop pet's Codex or Claude Code hooks."""

import sys

from desktop_pet.hook_install import (
    build_hooks, install_claude_hooks, install_hooks, merge_hooks, target_path,
)


def main() -> None:
    if sys.argv[1:] == ["--claude"]:
        target, changed = install_claude_hooks()
        print(f"{'Installed' if changed else 'Already up to date'} desktop pet hooks in {target}")
        print("New Claude Code sessions will use the hooks; check them with /hooks.")
        return
    target, changed = install_hooks()
    print(f"{'Installed' if changed else 'Already up to date'} desktop pet hooks in {target}")
    print("Review and trust the hooks in Codex with /hooks.")


if __name__ == "__main__":
    main()
