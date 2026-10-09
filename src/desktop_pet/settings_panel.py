from __future__ import annotations

import os
from uuid import uuid4
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from desktop_pet.config import PROJECT_ROOT
from desktop_pet.hook_install import install_hooks


class SettingsPanel(QDialog):
    scale_changed = Signal(int)
    fps_changed = Signal(int)
    stop_requested = Signal()
    hook_test_requested = Signal(str, str, str, str)

    def __init__(self, scale: int, fps: int, preview: QPixmap):
        super().__init__()
        self.setWindowTitle("桌寵設定")
        self.setWindowFlag(Qt.WindowType.Window)
        self.setWindowIcon(QIcon(str(PROJECT_ROOT / "icon.png")))
        self.setFixedWidth(650)
        self.setObjectName("settingsPanel")
        self._set_chinese_font()
        self._test_session_id = f"desktop-pet-test-{uuid4().hex}"
        self._test_turn_number = 0
        self._test_turn_id = ""

        shell = QHBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(158)
        navigation = QVBoxLayout(sidebar)
        navigation.setContentsMargins(14, 28, 14, 20)
        navigation.setSpacing(8)
        navigation_title = QLabel("桌寵控制")
        navigation_title.setObjectName("navigationTitle")
        navigation.addWidget(navigation_title)
        navigation.addSpacing(18)
        self.settings_button = QPushButton("設定")
        self.hook_button = QPushButton("Hook 測試")
        self.hook_settings_button = QPushButton("Hook 設定")
        for button in (self.settings_button, self.hook_button, self.hook_settings_button):
            button.setObjectName("navigationButton")
            button.setCheckable(True)
            navigation.addWidget(button)
        navigation.addStretch()
        shell.addWidget(sidebar)

        self.pages = QStackedWidget()
        shell.addWidget(self.pages, 1)
        self.settings_button.clicked.connect(lambda: self._show_page(0))
        self.hook_button.clicked.connect(lambda: self._show_page(1))
        self.hook_settings_button.clicked.connect(lambda: self._show_page(2))

        settings_page = QWidget()
        root = QVBoxLayout(settings_page)
        root.setContentsMargins(28, 26, 28, 24)
        root.setSpacing(18)
        self.pages.addWidget(settings_page)

        eyebrow = QLabel("DESKTOP PET  /  CONTROL CENTER")
        eyebrow.setObjectName("eyebrow")
        root.addWidget(eyebrow)

        heading = QHBoxLayout()
        heading.setSpacing(16)
        avatar = QLabel()
        avatar.setObjectName("avatar")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(66, 66)
        avatar.setPixmap(
            preview.scaled(
                48, 58,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        heading.addWidget(avatar)
        titles = QVBoxLayout()
        titles.setSpacing(3)
        title = QLabel("角色設定")
        title.setObjectName("title")
        subtitle = QLabel("調整桌面夥伴的顯示方式")
        subtitle.setObjectName("subtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        heading.addLayout(titles, 1)
        root.addLayout(heading)

        status_card = QFrame()
        status_card.setObjectName("settingCard")
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(19, 16, 19, 16)
        status_labels = QVBoxLayout()
        status_labels.setSpacing(4)
        status_title = QLabel("目前狀態")
        status_title.setObjectName("settingTitle")
        self.status_value = QLabel("閒置")
        self.status_value.setObjectName("statusValue")
        status_labels.addWidget(status_title)
        status_labels.addWidget(self.status_value)
        status_layout.addLayout(status_labels, 1)
        count_labels = QVBoxLayout()
        count_labels.setSpacing(4)
        count_title = QLabel("執行中的工作")
        count_title.setObjectName("description")
        self.active_count_value = QLabel("0")
        self.active_count_value.setObjectName("activeCountValue")
        count_labels.addWidget(count_title)
        count_labels.addWidget(self.active_count_value)
        status_layout.addLayout(count_labels)
        root.addWidget(status_card)

        self.scale_slider, self.scale_spin = self._add_setting(
            root, "角色大小", "變更桌面上的角色尺寸", "%", 50, 200, scale
        )
        self.fps_slider, self.fps_spin = self._add_setting(
            root, "動畫速度", "每秒播放的畫格數", " FPS", 4, 60, fps
        )
        self.scale_slider.valueChanged.connect(self.scale_changed)
        self.fps_slider.valueChanged.connect(self.fps_changed)

        note = QLabel("設定會自動儲存，下次啟動時繼續使用。")
        note.setObjectName("note")
        root.addWidget(note)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        close_button = QPushButton("關閉面板")
        close_button.setObjectName("secondaryButton")
        close_button.clicked.connect(self.close)
        stop_button = QPushButton("停止運行")
        stop_button.setObjectName("dangerButton")
        stop_button.clicked.connect(self.stop_requested)
        footer.addWidget(close_button, 1)
        footer.addWidget(stop_button, 1)
        root.addLayout(footer)

        hook_page = QWidget()
        hook_layout = QVBoxLayout(hook_page)
        hook_layout.setContentsMargins(28, 26, 28, 24)
        hook_layout.setSpacing(16)
        hook_eyebrow = QLabel("DESKTOP PET  /  HOOK TEST")
        hook_eyebrow.setObjectName("eyebrow")
        hook_layout.addWidget(hook_eyebrow)
        hook_title = QLabel("Hook 測試")
        hook_title.setObjectName("title")
        hook_layout.addWidget(hook_title)
        hook_hint = QLabel("點選事件，模擬 Codex hook 並觀察桌寵動畫。")
        hook_hint.setObjectName("subtitle")
        hook_hint.setWordWrap(True)
        hook_layout.addWidget(hook_hint)
        for label, event_name, description in (
            ("送出提示", "turn.started", "開始新回合，進入工作中"),
            ("工具開始", "tool.started", "播放操作工具動畫"),
            ("工具執行後", "turn.in_progress", "持續工作中的動畫"),
            ("請求授權", "action_required", "進入等待授權的動畫"),
            ("回合完成", "turn.completed", "播放完成動畫及測試回覆"),
            ("回合失敗", "turn.failed", "播放失敗動畫"),
            ("中斷回合", "turn.cancelled", "播放取消動畫"),
            ("結束工作階段", "session.ended", "回到閒置動畫"),
        ):
            button = QPushButton(f"{label}  ·  {description}")
            button.setObjectName("eventButton")
            button.clicked.connect(
                lambda checked=False, event=event_name: self._send_test_event(event)
            )
            hook_layout.addWidget(button)
        self.test_message = QLineEdit("這是一則 Hook 測試回覆")
        self.test_message.setPlaceholderText("回合完成時顯示的回覆內容")
        self.test_message.setMaxLength(100)
        hook_layout.addWidget(self.test_message)
        self.change_test_button = QPushButton("變更統計測試  ·  變更 1 個檔案 +1 -1")
        self.change_test_button.setObjectName("eventButton")
        self.change_test_button.clicked.connect(
            lambda: self._send_test_event(
                "turn.completed", "測試回覆\n變更 1 個檔案 +1 -1"
            )
        )
        hook_layout.addWidget(self.change_test_button)
        hook_layout.addStretch()
        hook_note = QLabel("測試事件會送至本機桌寵監聽器，不會觸發 Codex 工作。")
        hook_note.setObjectName("note")
        hook_note.setWordWrap(True)
        hook_layout.addWidget(hook_note)
        hook_close = QPushButton("關閉面板")
        hook_close.setObjectName("secondaryButton")
        hook_close.clicked.connect(self.close)
        hook_layout.addWidget(hook_close)
        self.pages.addWidget(hook_page)

        hook_settings_page = QWidget()
        hook_settings_layout = QVBoxLayout(hook_settings_page)
        hook_settings_layout.setContentsMargins(28, 26, 28, 24)
        hook_settings_layout.setSpacing(16)
        hook_settings_eyebrow = QLabel("DESKTOP PET  /  HOOK SETUP")
        hook_settings_eyebrow.setObjectName("eyebrow")
        hook_settings_layout.addWidget(hook_settings_eyebrow)
        hook_settings_title = QLabel("Hook 設定")
        hook_settings_title.setObjectName("title")
        hook_settings_layout.addWidget(hook_settings_title)
        hook_settings_hint = QLabel("將桌寵 Hook 加入目前使用者的 Codex 設定。")
        hook_settings_hint.setObjectName("subtitle")
        hook_settings_hint.setWordWrap(True)
        hook_settings_layout.addWidget(hook_settings_hint)
        self.install_hook_button = QPushButton("設定／更新 Hook")
        self.install_hook_button.setObjectName("eventButton")
        self.install_hook_button.clicked.connect(self._install_hooks)
        hook_settings_layout.addWidget(self.install_hook_button)
        self.hook_install_result = QLabel("")
        self.hook_install_result.setObjectName("note")
        self.hook_install_result.setWordWrap(True)
        hook_settings_layout.addWidget(self.hook_install_result)
        hook_settings_layout.addStretch()
        self.pages.addWidget(hook_settings_page)
        self._show_page(0)

        self.setStyleSheet("""
            QDialog#settingsPanel {
                background: #101827;
                color: #f3f7fb;
                font-family: "Noto Sans TC", "Microsoft JhengHei", "Segoe UI";
                font-size: 13px;
            }
            QFrame#sidebar { background: #172334; border-right: 1px solid #2d3c4f; }
            QLabel#navigationTitle { color: #67d7c0; font-size: 15px; font-weight: 700; }
            QPushButton#navigationButton {
                color: #bdcbd9; background: transparent; border: none;
                text-align: left; padding: 12px; border-radius: 9px;
            }
            QPushButton#navigationButton:hover { background: #263548; }
            QPushButton#navigationButton:checked { background: #28534f; color: #ecfffa; }
            QLabel { color: #edf4f9; background: transparent; }
            QLabel#eyebrow { color: #67d7c0; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
            QLabel#title { font-size: 25px; font-weight: 700; }
            QLabel#subtitle, QLabel#description, QLabel#note { color: #94a6b8; }
            QLabel#note { padding-left: 3px; font-size: 11px; }
            QLabel#avatar { background: #1b2d3a; border: 1px solid #355464; border-radius: 17px; }
            QFrame#settingCard {
                background: #1b2737;
                border: 1px solid #2d3c4f;
                border-radius: 16px;
            }
            QLabel#settingTitle { font-size: 15px; font-weight: 700; }
            QLabel#statusValue { color: #67d7c0; font-size: 14px; font-weight: 700; }
            QLabel#activeCountValue { color: #67d7c0; font-size: 22px; font-weight: 700; }
            QSpinBox {
                background: #111c2b;
                color: #ecf9f6;
                border: 1px solid #365263;
                border-radius: 9px;
                padding: 6px 8px;
                min-width: 74px;
                font-size: 13px;
                font-weight: 700;
            }
            QSpinBox:focus { border-color: #6bd8c1; }
            QSlider::groove:horizontal { height: 6px; background: #344455; border-radius: 3px; }
            QSlider::sub-page:horizontal { background: #66d4bd; border-radius: 3px; }
            QSlider::handle:horizontal {
                background: #ecfffa; border: 3px solid #66d4bd;
                width: 16px; margin: -8px 0; border-radius: 11px;
            }
            QPushButton { border-radius: 11px; padding: 11px; font-size: 13px; font-weight: 700; }
            QPushButton#secondaryButton { background: #263548; color: #dce8f2; border: 1px solid #3a5065; }
            QPushButton#secondaryButton:hover { background: #33465a; }
            QPushButton#dangerButton { background: #713f4c; color: #ffe6e8; border: 1px solid #a15868; }
            QPushButton#dangerButton:hover { background: #8b4a5a; }
            QPushButton#eventButton {
                background: #1b2737; color: #edf4f9; border: 1px solid #2d3c4f;
                text-align: left; padding: 11px 14px;
            }
            QPushButton#eventButton:hover { background: #28534f; border-color: #67d7c0; }
            QLineEdit {
                background: #111c2b; color: #ecf9f6; border: 1px solid #365263;
                border-radius: 9px; padding: 9px;
            }
            QLineEdit:focus { border-color: #6bd8c1; }
        """)

    def _show_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self.settings_button.setChecked(index == 0)
        self.hook_button.setChecked(index == 1)
        self.hook_settings_button.setChecked(index == 2)

    def _install_hooks(self) -> None:
        try:
            target, changed = install_hooks()
        except (OSError, ValueError) as error:
            self.hook_install_result.setText(f"設定失敗：{error}")
            return
        result = "Hook 已設定／更新。" if changed else "Hook 已是最新設定。"
        self.hook_install_result.setText(
            f"{result}\n位置：{target}\n請到 Codex 輸入 /hooks，審閱並信任新增的 Hook。"
        )

    def _send_test_event(self, event_name: str, message_override: str | None = None) -> None:
        if event_name == "turn.started" or (
            not self._test_turn_id and event_name != "session.ended"
        ):
            self._test_turn_number += 1
            self._test_turn_id = f"turn-{self._test_turn_number}"
        message = (
            message_override if message_override is not None
            else self.test_message.text() if event_name == "turn.completed" else ""
        )
        self.hook_test_requested.emit(
            event_name, message, self._test_session_id, self._test_turn_id
        )
        if event_name in {"turn.completed", "turn.failed", "turn.cancelled", "session.ended"}:
            self._test_turn_id = ""

    def set_work_status(self, status: str, active_count: int) -> None:
        self.status_value.setText(status)
        self.active_count_value.setText(str(active_count))

    def _set_chinese_font(self) -> None:
        font_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        for filename in ("NotoSansTC-VF.ttf", "msjh.ttc"):
            font_path = font_dir / filename
            if font_path.exists():
                font_id = QFontDatabase.addApplicationFont(str(font_path))
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    self.setFont(QFont(families[0], 10))
                    return

    @staticmethod
    def _add_setting(
        root: QVBoxLayout,
        title: str,
        description: str,
        suffix: str,
        minimum: int,
        maximum: int,
        value: int,
    ) -> tuple[QSlider, QSpinBox]:
        card = QFrame()
        card.setObjectName("settingCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(19, 16, 19, 18)
        layout.setSpacing(12)
        header = QHBoxLayout()
        labels = QVBoxLayout()
        labels.setSpacing(3)
        name = QLabel(title)
        name.setObjectName("settingTitle")
        hint = QLabel(description)
        hint.setObjectName("description")
        labels.addWidget(name)
        labels.addWidget(hint)
        header.addLayout(labels, 1)
        spin = QSpinBox()
        spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        spin.setRange(minimum, maximum)
        spin.setSuffix(suffix)
        spin.setValue(value)
        header.addWidget(spin)
        layout.addLayout(header)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        slider.valueChanged.connect(spin.setValue)
        spin.valueChanged.connect(slider.setValue)
        layout.addWidget(slider)
        root.addWidget(card)
        return slider, spin
