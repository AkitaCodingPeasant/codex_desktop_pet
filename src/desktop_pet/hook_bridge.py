from __future__ import annotations

import json
import re
import socket
import sys

from PySide6.QtGui import QTextDocument


HOST = "127.0.0.1"
PORT = 49377
MAX_REPLY_CHARS = 100
CODEX_EVENTS = {
    "UserPromptSubmit": "turn.started",
    "PostToolUse": "turn.in_progress",
    "PermissionRequest": "action_required",
    "Stop": "turn.completed",
    "Interrupt": "turn.cancelled",
    "SessionEnd": "session.ended",
}
USER_INPUT_TOOLS = frozenset({"request_user_input", "request_user_input_async"})
PET_EVENTS = frozenset((
    *CODEX_EVENTS.values(), "turn.failed", "user_input_requested",
    "user_input_completed", "tool.started",
))


def event_for_hook(payload: dict) -> str | None:
    hook_name = payload.get("hook_event_name")
    tool_name = payload.get("tool_name")
    tool_name = tool_name.rsplit(".", 1)[-1] if isinstance(tool_name, str) else ""
    if hook_name == "PreToolUse":
        return "user_input_requested" if tool_name in USER_INPUT_TOOLS else "tool.started"
    if hook_name == "PostToolUse" and tool_name == "request_user_input_async":
        return None
    if hook_name == "PostToolUse" and tool_name == "request_user_input":
        return "user_input_completed"
    return CODEX_EVENTS.get(hook_name)


def _plain_reply(message: str) -> str:
    message = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", message)
    document = QTextDocument()
    document.setMarkdown(message)
    return " ".join(document.toPlainText().split())


def reply_preview(message: str) -> str:
    plain_text = _plain_reply(message)
    if len(plain_text) > MAX_REPLY_CHARS:
        return plain_text[:MAX_REPLY_CHARS] + "..."
    return plain_text


def completion_preview(message: str) -> str:
    plain_text = _plain_reply(message)
    files = re.search(
        r"(?:已)?(?:更動|變更|修改)\s*(\d+)\s*個?檔案|(?:已)?(?:更動|變更|修改)檔案(?:數)?\s*[:：]?\s*(\d+)",
        plain_text,
    )
    if files is None:
        return reply_preview(message)
    compact = re.match(r"\s*[+＋](\d+)\s*[-−－](\d+)(?:\s*行)?", plain_text[files.end():])
    if compact:
        added_count, removed_count = compact.groups()
        end = files.end() + compact.end()
    else:
        added = re.search(r"新增(?:行數)?\s*[:：]?\s*(\d+)\s*行?", plain_text[files.end():])
        removed = re.search(r"(?:刪除|刪減)(?:行數)?\s*[:：]?\s*(\d+)\s*行?", plain_text[files.end():])
        if not added or not removed:
            return reply_preview(message)
        added_count, removed_count = added[1], removed[1]
        end = files.end() + max(added.end(), removed.end())
    summary = f"已變更 {files[1] or files[2]} 個檔案 +{added_count} -{removed_count}"
    reply = " ".join((plain_text[:files.start()] + plain_text[end:]).split())
    reply = reply.strip(" ，,、｜|;；:：。")
    preview = reply[:MAX_REPLY_CHARS] + ("..." if len(reply) > MAX_REPLY_CHARS else "")
    return f"{preview}\n{summary}" if preview else summary


def send_event(
    event_name: str, message: str = "", session_id: str = "", turn_id: str = ""
) -> None:
    if event_name not in PET_EVENTS:
        raise ValueError(f"Unknown pet event: {event_name}")
    preview = completion_preview(message) if event_name == "turn.completed" else message[:MAX_REPLY_CHARS]
    packet = json.dumps(
        {
            "event": event_name,
            "message": preview,
            "session_id": session_id,
            "turn_id": turn_id,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
        sender.sendto(packet, (HOST, PORT))


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--event":
        send_event(sys.argv[2])
        return

    hook_name = None
    try:
        payload = json.load(sys.stdin.buffer)
        hook_name = payload.get("hook_event_name")
        event_name = event_for_hook(payload)
        if event_name is not None:
            message = payload.get("last_assistant_message") if hook_name == "Stop" else None
            session_id = payload.get("session_id")
            turn_id = payload.get("turn_id")
            send_event(
                event_name,
                message if isinstance(message, str) else "",
                session_id if isinstance(session_id, str) else "",
                turn_id if isinstance(turn_id, str) else "",
            )
    except (OSError, ValueError, TypeError, AttributeError):
        # A desktop notification must never alter the Codex turn.
        pass
    if hook_name == "Stop":
        print("{}")


if __name__ == "__main__":
    main()
