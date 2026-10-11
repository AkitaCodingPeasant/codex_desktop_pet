from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from desktop_pet.config import read_simple_yaml


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IntroConfig:
    folder: Path
    fps: int
    scale_percent: int
    x: float
    y: float


def load_intro_config(path: Path) -> IntroConfig:
    data = read_simple_yaml(path)
    folder_value = data.get("folder", "Intro")
    if not isinstance(folder_value, str) or not folder_value.strip():
        raise ValueError(f"{path}: folder must be a directory path")
    folder = Path(folder_value).expanduser()
    if not folder.is_absolute():
        folder = path.parent / folder

    try:
        fps = int(data.get("fps", 24))
        scale_percent = int(data.get("scale_percent", 100))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{path}: fps and scale_percent must be integers") from error
    if fps <= 0 or scale_percent <= 0:
        raise ValueError(f"{path}: fps and scale_percent must be greater than zero")
    try:
        x = float(data.get("x", 0.5))
        y = float(data.get("y", 0.5))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{path}: x and y must be numbers from 0 to 1") from error
    if not (math.isfinite(x) and math.isfinite(y) and 0 <= x <= 1 and 0 <= y <= 1):
        raise ValueError(f"{path}: x and y must be numbers from 0 to 1")
    return IntroConfig(folder.resolve(), fps, scale_percent, x, y)


def position_on_screen(area: QRect, width: int, height: int, x: float, y: float) -> QPoint:
    return QPoint(
        area.left() + round((area.width() - width) * x),
        area.top() + round((area.height() - height) * y),
    )


class StartupAnimation(QWidget):
    finished = Signal()

    def __init__(self, config_path: Path):
        super().__init__()
        self.config_path = config_path
        self.config: IntroConfig | None = None
        self.frame_paths: list[Path] = []
        self.frame_index = 0
        self._finished = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.label = QLabel(self)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self._show_next_frame)
        self.clock = QElapsedTimer()

    def start(self) -> None:
        self.timer.stop()
        self.clock.invalidate()
        self.frame_index = 0
        self._finished = False
        try:
            self.config = load_intro_config(self.config_path)
        except (OSError, ValueError) as error:
            logger.warning("Could not load intro settings: %s", error)
            self._finish()
            return

        self.frame_paths = sorted(self.config.folder.glob("*.png"))
        if not self.frame_paths:
            logger.warning("No startup animation frames found in %s", self.config.folder)
            self._finish()
            return

        first_frame = QImageReader(str(self.frame_paths[0]))
        size = first_frame.size()
        screen = QApplication.primaryScreen()
        if not size.isValid() or screen is None:
            logger.warning("Could not initialize startup animation in %s", self.config.folder)
            self._finish()
            return

        area = screen.geometry()
        base_scale = min(1.0, area.width() * 0.85 / size.width(),
                         area.height() * 0.85 / size.height())
        scale = min(base_scale * self.config.scale_percent / 100,
                    area.width() / size.width(), area.height() / size.height())
        self.setFixedSize(max(1, round(size.width() * scale)),
                          max(1, round(size.height() * scale)))
        self.label.setFixedSize(self.size())
        self.move(position_on_screen(area, self.width(), self.height(),
                                     self.config.x, self.config.y))
        self._show_next_frame()

    def _show_next_frame(self) -> None:
        if self.clock.isValid():
            elapsed_frame = int(self.clock.elapsed() * self.config.fps / 1000)
            self.frame_index = max(self.frame_index, elapsed_frame)
        if self.frame_index >= len(self.frame_paths):
            self._finish()
            return

        reader = QImageReader(str(self.frame_paths[self.frame_index]))
        reader.setScaledSize(self.size())
        frame = reader.read()
        if frame.isNull():
            logger.warning("Could not read startup frame %s: %s",
                           self.frame_paths[self.frame_index], reader.errorString())
            self._finish()
            return

        self.label.setPixmap(QPixmap.fromImage(frame))
        if not self.clock.isValid():
            self.show()
            self.clock.start()
        self.frame_index += 1
        next_frame_ms = round(self.frame_index * 1000 / self.config.fps)
        self.timer.start(max(1, next_frame_ms - self.clock.elapsed()))

    def _finish(self) -> None:
        if self._finished:
            return
        self._finished = True
        self.timer.stop()
        self.hide()
        self.finished.emit()
