from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect, QTimer, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop_pet.startup_animation import StartupAnimation, load_intro_config, position_on_screen


class StartupAnimationTests(unittest.TestCase):
    def test_left_click_skips_intro_once(self) -> None:
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frames = root / "frames"
            frames.mkdir()
            image = QImage(100, 100, QImage.Format.Format_ARGB32)
            image.fill(QColor(255, 0, 0))
            for index in range(2):
                self.assertTrue(image.save(str(frames / f"{index:04}.png")))
            settings = root / "intro.yaml"
            settings.write_text("folder: frames\nfps: 1\n", encoding="utf-8")
            intro = StartupAnimation(settings)
            finished = []
            intro.finished.connect(lambda: finished.append(True))
            try:
                intro.start()
                self.assertTrue(intro.isVisible())
                QTest.mouseClick(intro, Qt.MouseButton.LeftButton)
                self.assertEqual(finished, [True])
                self.assertFalse(intro.isVisible())
                self.assertFalse(intro.timer.isActive())
                intro._finish()
                self.assertEqual(finished, [True])
            finally:
                intro.close()

    def test_settings_control_folder_fps_and_scale(self) -> None:
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frames = root / "frames"
            frames.mkdir()
            image = QImage(100, 100, QImage.Format.Format_ARGB32)
            image.fill(QColor(0, 0, 0, 0))
            self.assertTrue(image.save(str(frames / "0001.png")))
            self.assertTrue(image.save(str(frames / "0002.png")))
            settings = root / "intro.yaml"
            settings.write_text(
                "folder: frames\nfps: 10\nscale_percent: 50\nx: 1\ny: 1\n",
                encoding="utf-8",
            )

            intro = StartupAnimation(settings)
            finished = []
            intro.finished.connect(lambda: (finished.append(intro.clock.elapsed()), app.quit()))
            intro.start()
            self.assertEqual(intro.size().width(), 50)
            self.assertEqual(intro.size().height(), 50)
            area = app.primaryScreen().geometry()
            self.assertEqual(intro.pos(), QPoint(area.right() - 49, area.bottom() - 49))
            self.assertTrue(intro.label.pixmap().toImage().hasAlphaChannel())
            QTimer.singleShot(1000, app.quit)
            app.exec()
            self.assertEqual(len(finished), 1)
            self.assertGreaterEqual(finished[0], 180)
            self.assertLess(finished[0], 900)

            settings.write_text(
                "folder: frames\nfps: 20\nscale_percent: 80\nx: 0\ny: 0\n",
                encoding="utf-8",
            )
            intro.start()
            self.assertEqual(intro.size().width(), 80)
            self.assertEqual(intro.pos(), area.topLeft())
            QTimer.singleShot(1000, app.quit)
            app.exec()
            self.assertEqual(len(finished), 2)
            self.assertGreaterEqual(finished[1], 90)
            self.assertLess(finished[1], 900)
            intro.close()

    def test_normalized_positions(self) -> None:
        area = QRect(100, 200, 800, 600)
        self.assertEqual(position_on_screen(area, 100, 50, 0, 0), QPoint(100, 200))
        self.assertEqual(position_on_screen(area, 100, 50, 0.5, 0.5), QPoint(450, 475))
        self.assertEqual(position_on_screen(area, 100, 50, 1, 1), QPoint(800, 750))
        self.assertEqual(position_on_screen(area, 100, 50, 0.2, 0.8), QPoint(240, 640))

    def test_position_must_be_within_zero_and_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = Path(temporary) / "intro.yaml"
            settings.write_text("x: 1.1\ny: 0.5\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "x and y"):
                load_intro_config(settings)


if __name__ == "__main__":
    unittest.main()
