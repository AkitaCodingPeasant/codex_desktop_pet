"""Send a desktop-pet event from any project's hook command."""

from __future__ import annotations

import argparse
import json
import socket
import sys


HOST = "127.0.0.1"
PORT = 49377
MAX_PACKET_BYTES = 4096
EVENTS = (
    "turn.started",
    "tool.started",
    "turn.in_progress",
    "action_required",
    "user_input_requested",
    "user_input_completed",
    "turn.completed",
    "turn.failed",
    "turn.cancelled",
    "session.ended",
)


def build_packet(
    event: str, title: str, message: str, session_id: str, turn_id: str
) -> bytes:
    packet = json.dumps(
        {
            "event": event,
            "title": title,
            "message": message,
            "session_id": session_id,
            "turn_id": turn_id,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    if len(packet) > MAX_PACKET_BYTES:
        raise ValueError(f"事件封包超過 {MAX_PACKET_BYTES} bytes，請縮短標題或訊息。")
    return packet


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pet-hook",
        description="將其他工具的 Hook 事件送至本機桌寵。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "範例（CMD）：\n"
            "  pet-hook turn.started --title \"VideoTool\" --message \"正在產生影片\" "
            "--session-id video:project-a --turn-id job-001\n"
            "  pet-hook tool.started --session-id video:project-a --turn-id job-001\n"
            "  pet-hook turn.in_progress --session-id video:project-a --turn-id job-001\n"
            "  pet-hook turn.completed --message \"影片處理完成\" "
            "--session-id video:project-a --turn-id job-001\n"
            "\n--title 可省略；同一回合請沿用相同的 session-id 與 turn-id。"
        ),
    )
    parser.add_argument("event", choices=EVENTS, help="桌寵事件名稱")
    parser.add_argument("--title", default="", help="工作清單標題，可省略")
    parser.add_argument("--message", default="", help="工作訊息或完成回覆")
    parser.add_argument("--session-id", required=True, help="工具的工作階段 ID")
    parser.add_argument("--turn-id", default="", help="本次工作的回合 ID")
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    if not args.session_id.strip():
        parser.error("--session-id 不可為空")
    if args.event != "session.ended" and not args.turn_id.strip():
        parser.error("此事件必須提供 --turn-id")

    try:
        packet = build_packet(
            args.event, args.title, args.message, args.session_id, args.turn_id
        )
    except ValueError as error:
        parser.error(str(error))

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            sender.sendto(packet, (HOST, PORT))
    except OSError as error:
        print(f"無法送出桌寵事件：{error}", file=sys.stderr)
        return 0  # A notification must not fail the calling tool's hook.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
