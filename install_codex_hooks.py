"""Command-line entry point for installing the desktop pet's Codex hooks."""

from desktop_pet.hook_install import build_hooks, install_hooks, merge_hooks, target_path


def main() -> None:
    target, changed = install_hooks()
    print(f"{'Installed' if changed else 'Already up to date'} desktop pet hooks in {target}")
    print("Review and trust the hooks in Codex with /hooks.")


if __name__ == "__main__":
    main()
