from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPRITESHEET_CONFIG_PATH = PROJECT_ROOT / "assets" / "spritesheet.yaml"


@dataclass(frozen=True)
class Animation:
    row: int
    frames: int
    fps: int = 8
    sequence: tuple[int, ...] = ()

    @property
    def frame_sequence(self) -> tuple[int, ...]:
        if self.sequence:
            return self.sequence
        return tuple(range(self.frames))


@dataclass(frozen=True)
class SpriteSheetConfig:
    image_path: Path
    frame_width: int
    frame_height: int
    animations: dict[str, Animation]


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        items = value[1:-1].strip()
        if not items:
            return []
        return [_parse_scalar(item) for item in items.split(",")]
    if value.isdigit():
        return int(value)
    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value.startswith(("'", '"'))
    ):
        return value[1:-1]
    return value


def read_simple_yaml(path: Path) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        1,
    ):
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"{path}:{line_number}: expected 'key: value'")

        indent = len(line) - len(line.lstrip(" "))
        key, value = line.strip().split(":", 1)

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if value.strip():
            parent[key] = _parse_scalar(value)
        else:
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))

    return root


def load_spritesheet_config(path: Path = SPRITESHEET_CONFIG_PATH) -> SpriteSheetConfig:
    data = read_simple_yaml(path)
    frame = data["frame"]
    animations = {
        name: _load_animation(name, animation, int(data.get("fps", 8)), path)
        for name, animation in data["animations"].items()
    }

    return SpriteSheetConfig(
        image_path=(path.parent / str(data["image"])).resolve(),
        frame_width=int(frame["width"]),
        frame_height=int(frame["height"]),
        animations=animations,
    )


def _load_animation(
    name: str,
    data: dict[str, Any],
    default_fps: int,
    path: Path,
) -> Animation:
    row = int(data["row"])
    frames = int(data["frames"])
    fps = int(data.get("fps", default_fps))
    sequence = tuple(int(frame_index) for frame_index in data.get("sequence", ()))

    if row <= 0:
        raise ValueError(f"{path}: animations.{name}.row must be greater than 0")
    if frames <= 0:
        raise ValueError(f"{path}: animations.{name}.frames must be greater than 0")
    if fps <= 0:
        raise ValueError(f"{path}: animations.{name}.fps must be greater than 0")
    if any(frame_index < 0 or frame_index >= frames for frame_index in sequence):
        raise ValueError(
            f"{path}: animations.{name}.sequence frame index must be between "
            f"0 and {frames - 1}"
        )

    return Animation(
        row=row,
        frames=frames,
        fps=fps,
        sequence=sequence,
    )

