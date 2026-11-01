# -*- coding: utf-8 -*-
"""小说广告清理工具 2.0

在 TXT 小说中检索广告语句，人工复核检索结果后生成去广告副本。
所有文本处理由 adclean_core 完成；本模块只负责 PyQt5 界面与交互。
"""

from __future__ import annotations

import ctypes
import html
import json
import math
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from string import Template
from typing import List, Optional, Set, Tuple

from PyQt5.QtCore import (
    QCoreApplication,
    QRectF,
    QSettings,
    QSize,
    Qt,
    QThread,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontMetrics,
    QIcon,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
)
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import adclean_core as core

APP_NAME = "小说广告清理工具"
APP_VERSION = "2.0.0"
SETTINGS_DIR_ENV = "TXT_AD_CLEAN_SETTINGS_DIR"
FONT_FAMILY = "Microsoft YaHei UI"
DEFAULT_FONT_SIZE = 15
MIN_FONT_SIZE = 12
MAX_FONT_SIZE = 20
BASE_FONT_SIZE = 13

QUERY_PRESETS = [
    ("网址 / 链接", "http OR www OR .com OR .net OR .cn OR 网址"),
    ("公众号 / 扫码", "公众号 OR 微信号 OR 扫码 OR 关注"),
    ("求书 / 加群", "求书 OR 书友群 OR QQ群 OR 加群"),
    ("盗版站 / 全文阅读", "笔趣阁 OR 最新章节 OR 首发 OR 全文阅读"),
    ("HTML 闭合标签", "</a> OR </strong> OR </span> OR </div>"),
    ("下一页 / 未完", "本章未完 OR 点击下一页 OR 继续阅读"),
]

SAMPLE_TEXT = (
    "夜色渐深，他合上书本。\n"
    "“明天见！”她挥了挥手。\n"
    '更多精彩，请访问 <a href="http://example.com">www.example.com</a></strong>\n'
    "关注公众号「书友之家」，回复“领书”即可阅读全文》\n"
    "本章未完，点击下一页继续阅读】"
)

ENCODING_LABELS = {
    "utf-8-sig": "UTF-8 BOM",
    "utf-8": "UTF-8",
    "gbk": "GBK",
    "gb18030": "GB18030",
    "big5": "Big5",
    "utf-16": "UTF-16",
    "utf-16-le": "UTF-16 LE",
    "utf-16-be": "UTF-16 BE",
}

OUTPUT_ENCODINGS = [
    ("UTF-8（带 BOM，推荐）", "utf-8-sig"),
    ("UTF-8（无 BOM）", "utf-8"),
    ("跟随原文件", "source"),
    ("GB18030", "gb18030"),
]


def _system_prefers_dark():
    if sys.platform != "win32":
        return False
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return int(value) == 0
    except Exception:
        return False


def _settings_path():
    override = os.environ.get(SETTINGS_DIR_ENV)
    base = override or os.path.join(
        os.environ.get("APPDATA") or os.path.expanduser("~"), "TXTAdCleaner"
    )
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "settings.ini")


def _windows_app_id():
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Dayrk0.TXTAdCleaner.2"
        )
    except Exception:
        pass


def build_app_icon():
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(_icon_pixmap(size))
    return icon


def _icon_pixmap(size):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)
    painter.scale(size / 256.0, size / 256.0)

    background = QPainterPath()
    background.addRoundedRect(QRectF(8, 8, 240, 240), 56, 56)
    gradient = QLinearGradient(8, 8, 248, 248)
    gradient.setColorAt(0.0, QColor("#2563EB"))
    gradient.setColorAt(1.0, QColor("#7C3AED"))
    painter.fillPath(background, gradient)

    shadow = QPainterPath()
    shadow.addRoundedRect(QRectF(70, 50, 124, 152), 14, 14)
    painter.fillPath(shadow, QColor(15, 23, 42, 60))

    document = QPainterPath()
    document.addRoundedRect(QRectF(66, 44, 124, 152), 14, 14)
    painter.fillPath(document, QColor("#FFFFFF"))

    fold = QPainterPath()
    fold.moveTo(190, 44)
    fold.lineTo(190, 78)
    fold.lineTo(156, 44)
    fold.closeSubpath()
    painter.fillPath(fold, QColor("#DBEAFE"))

    painter.setPen(QPen(QColor("#93C5FD"), 8, Qt.SolidLine, Qt.RoundCap))
    for y, width in ((88, 70), (114, 82), (140, 58)):
        painter.drawLine(84, y, 84 + width, y)

    star = QPainterPath()
    center_x, center_y = 196.0, 196.0
    for index in range(8):
        angle = math.pi / 4 * index - math.pi / 2
        radius = 32.0 if index % 2 == 0 else 8.0
        point_x = center_x + math.cos(angle) * radius
        point_y = center_y + math.sin(angle) * radius
        if index == 0:
            star.moveTo(point_x, point_y)
        else:
            star.lineTo(point_x, point_y)
    star.closeSubpath()
    painter.fillPath(star, QColor("#FDE68A"))

    painter.end()
    return pixmap


THEMES = {
    "light": {
        "bg": "#F4F7FC",
        "surface": "#FFFFFF",
        "surface_alt": "#F7F9FD",
        "border": "#E2E8F2",
        "border_strong": "#C9D5E6",
        "text": "#172033",
        "muted": "#64748B",
        "primary": "#2563EB",
        "primary_hover": "#1D4ED8",
        "primary_soft": "#E8F0FE",
        "on_primary": "#FFFFFF",
        "danger": "#DC2626",
        "danger_hover": "#B91C1C",
        "danger_soft": "#FEF2F2",
        "on_danger": "#FFFFFF",
        "success": "#0F7B4A",
        "success_bg": "#ECFDF5",
        "success_text": "#065F46",
        "success_border": "#A7F3D0",
        "warning": "#B45309",
        "warning_soft": "#FFF7ED",
        "disabled_bg": "#C7D2E3",
        "disabled_text": "#64748B",
        "scroll": "#C7D2E3",
        "scroll_hover": "#94A3B8",
        "selection": "#DBEAFE",
        "code_bg": "#EEF2F7",
        "highlight_bg": "#FEF3C7",
        "highlight_text": "#92400E",
        "toast_bg": "#111827",
        "toast_text": "#F9FAFB",
        "shadow": "#0F172A",
    },
    "dark": {
        "bg": "#0B1220",
        "surface": "#121C2E",
        "surface_alt": "#17233A",
        "border": "#26344D",
        "border_strong": "#3A4C6B",
        "text": "#E6EDF8",
        "muted": "#93A4BD",
        "primary": "#60A5FA",
        "primary_hover": "#93C5FD",
        "primary_soft": "#1B3355",
        "on_primary": "#0B1220",
        "danger": "#F87171",
        "danger_hover": "#FCA5A5",
        "danger_soft": "#3A1D24",
        "on_danger": "#0B1220",
        "success": "#34D399",
        "success_bg": "#0F2E2A",
        "success_text": "#A7F3D0",
        "success_border": "#1F5A4E",
        "warning": "#FBBF24",
        "warning_soft": "#3A2A12",
        "disabled_bg": "#2B3A55",
        "disabled_text": "#7C8CA6",
        "scroll": "#33445F",
        "scroll_hover": "#4A5E7E",
        "selection": "#1E3A5F",
        "code_bg": "#0F1B2E",
        "highlight_bg": "#78350F",
        "highlight_text": "#FDE68A",
        "toast_bg": "#E2E8F0",
        "toast_text": "#0F172A",
        "shadow": "#000000",
    },
}

QSS_TEMPLATE = Template(
    """
QWidget {
    color: $text;
    font-size: $fs_base;
}
QMainWindow, QWidget#Root, QDialog {
    background-color: $bg;
}
QLabel {
    background: transparent;
}
QLabel#Title {
    font-size: $fs_title;
    font-weight: bold;
    color: $text;
}
QLabel#Subtitle {
    font-size: $fs_base;
    color: $muted;
}
QLabel#Version {
    background-color: $primary_soft;
    color: $primary;
    border-radius: 10px;
    padding: 3px 9px;
    font-size: $fs_small;
    font-weight: bold;
}
QFrame#Card {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 14px;
}
QLabel#Number {
    background-color: $primary_soft;
    color: $primary;
    border-radius: 13px;
    font-size: $fs_base;
    font-weight: bold;
}
QLabel#SectionTitle {
    font-size: $fs_section;
    font-weight: bold;
    color: $text;
}
QLabel#SectionSub {
    font-size: $fs_small;
    color: $muted;
}
QLabel#Hint {
    font-size: $fs_small;
    color: $muted;
}
QLabel#Hint[tone="success"] {
    color: $success;
}
QLabel#Hint[tone="error"] {
    color: $danger;
}
QLabel#FieldLabel {
    font-size: $fs_meta;
    font-weight: bold;
    color: $text;
}
QLabel#Badge {
    background-color: $primary_soft;
    color: $primary;
    border-radius: 10px;
    padding: 2px 9px;
    font-size: $fs_small;
    font-weight: bold;
}
QLabel#PanelTitle {
    font-size: $fs_panel;
    font-weight: bold;
}
QLabel#ResultStatus {
    background-color: $surface_alt;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 5px 11px;
    color: $muted;
    font-size: $fs_status;
    font-weight: bold;
}
QLabel#ResultStatus[tone="success"] {
    background-color: $success_bg;
    border-color: $success_border;
    color: $success;
}
QLabel#ResultStatus[tone="error"] {
    background-color: $danger_soft;
    border-color: $danger;
    color: $danger;
}
QLabel#ResultStatus[tone="warning"] {
    background-color: $warning_soft;
    border-color: $warning;
    color: $warning;
}
QLabel#Elapsed {
    color: $muted;
    font-size: $fs_meta;
}
QLabel#FooterStatus {
    color: $muted;
    font-size: $fs_meta;
}
QLabel#EmptyIcon {
    background-color: $primary_soft;
    color: $primary;
    border-radius: 18px;
    font-size: $fs_empty_icon;
    font-weight: bold;
}
QLabel#EmptyTitle {
    font-size: $fs_panel;
    font-weight: bold;
    color: $text;
}
QLabel#FileGlyph {
    background-color: $primary_soft;
    color: $primary;
    border-radius: 9px;
    font-size: $fs_small;
    font-weight: bold;
}
QLabel#FileName {
    font-size: $fs_file;
    font-weight: bold;
}
QFrame#DropZone {
    background-color: $surface_alt;
    border: 1px dashed $border_strong;
    border-radius: 10px;
}
QFrame#DropZone:hover {
    border-color: $primary;
    background-color: $primary_soft;
}
QFrame#DropZone[dragActive="true"] {
    border: 1px solid $primary;
    background-color: $primary_soft;
}
QFrame#DropZone:disabled {
    background-color: $bg;
    border-color: $border;
}
QLineEdit, QComboBox, QPlainTextEdit, QTextBrowser, QSpinBox {
    background-color: $surface_alt;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 6px 9px;
    selection-background-color: $selection;
    selection-color: $text;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTextBrowser:focus, QSpinBox:focus {
    border: 1px solid $primary;
}
QLineEdit:read-only {
    color: $text;
}
QLineEdit:disabled, QComboBox:disabled {
    color: $muted;
    background-color: $bg;
}
QComboBox {
    padding-right: 24px;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 4px;
    selection-background-color: $primary_soft;
    selection-color: $primary;
}
QComboBox QAbstractItemView::item {
    min-height: $fs_row_height;
    padding: 2px 8px;
}
QPushButton {
    background-color: $surface_alt;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 6px 12px;
    min-height: 20px;
}
QPushButton:hover {
    border-color: $primary;
    color: $primary;
}
QPushButton:pressed {
    background-color: $primary_soft;
}
QPushButton:disabled {
    background-color: $bg;
    color: $muted;
    border-color: $border;
}
QPushButton:focus {
    border: 1px solid $primary;
}
QPushButton#Primary {
    background-color: $primary;
    color: $on_primary;
    border: 1px solid $primary;
    font-weight: bold;
}
QPushButton#Primary:hover {
    background-color: $primary_hover;
    border-color: $primary_hover;
    color: $on_primary;
}
QPushButton#Primary:pressed {
    background-color: $primary_hover;
}
QPushButton#Primary:disabled {
    background-color: $disabled_bg;
    border-color: $disabled_bg;
    color: $disabled_text;
}
QPushButton#Primary[mode="cancel"] {
    background-color: $surface;
    color: $danger;
    border: 1px solid $danger;
}
QPushButton#Primary[mode="cancel"]:hover {
    background-color: $danger_soft;
    color: $danger;
}
QPushButton#Primary[mode="cancel"]:disabled {
    background-color: $bg;
    color: $muted;
    border-color: $border;
}
QPushButton#Danger {
    background-color: $danger;
    color: $on_danger;
    border: 1px solid $danger;
    font-weight: bold;
    font-size: $fs_danger;
}
QPushButton#Danger:hover {
    background-color: $danger_hover;
    border-color: $danger_hover;
    color: $on_danger;
}
QPushButton#Danger:disabled {
    background-color: $disabled_bg;
    border-color: $disabled_bg;
    color: $disabled_text;
}
QPushButton#Ghost {
    background-color: transparent;
}
QPushButton#Ghost:hover {
    background-color: $primary_soft;
    border-color: $primary;
}
QPushButton#Link {
    background: transparent;
    border: none;
    color: $primary;
    padding: 2px 4px;
}
QPushButton#Link:hover {
    color: $primary_hover;
}
QFrame#Divider {
    background-color: $border;
    border: none;
    min-height: 1px;
    max-height: 1px;
}
QTabWidget::pane {
    border: none;
    background: transparent;
}
QTabBar::tab {
    background: transparent;
    color: $muted;
    padding: 8px 14px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: $fs_base;
}
QTabBar::tab:selected {
    color: $primary;
    border-bottom: 2px solid $primary;
    font-weight: bold;
}
QTabBar::tab:hover {
    color: $text;
}
QProgressBar {
    background-color: $surface_alt;
    border: none;
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: $primary;
    border-radius: 4px;
}
QPlainTextEdit#Log {
    font-family: "Consolas";
    font-size: $fs_log;
    padding: 8px;
}
QTextBrowser#Preview {
    padding: 6px;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: $scroll;
    min-height: 28px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: $scroll_hover;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: $scroll;
    min-width: 28px;
    border-radius: 4px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
QTableWidget {
    background-color: $surface_alt;
    alternate-background-color: $surface;
    border: 1px solid $border;
    border-radius: 8px;
    gridline-color: $border;
}
QTableWidget::item {
    padding: 6px 8px;
}
QTableWidget::item:selected {
    background-color: $primary_soft;
    color: $primary;
}
QHeaderView::section {
    background-color: $surface;
    color: $muted;
    border: none;
    border-bottom: 1px solid $border;
    padding: 7px 8px;
    font-size: $fs_small;
    font-weight: bold;
}
QTableCornerButton::section {
    background-color: $surface;
    border: none;
}
QMenu {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 5px;
}
QMenu::item {
    padding: 7px 22px 7px 12px;
    border-radius: 5px;
}
QMenu::item:selected {
    background-color: $primary_soft;
    color: $primary;
}
QMenu::separator {
    height: 1px;
    background-color: $border;
    margin: 5px 8px;
}
QToolTip {
    background-color: $toast_bg;
    color: $toast_text;
    border: 1px solid $border;
    padding: 5px 8px;
}
QLabel#Toast {
    background-color: $toast_bg;
    color: $toast_text;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 10px 16px;
    font-size: $fs_base;
}
QLabel#Toast[kind="error"] {
    background-color: $danger;
    color: $on_danger;
    border-color: $danger;
}
QLabel#Toast[kind="success"] {
    background-color: $success_bg;
    color: $success_text;
    border-color: $success_border;
}
QMessageBox {
    background-color: $surface;
}
QMessageBox QLabel {
    color: $text;
}
"""
)


class ElidedLabel(QLabel):
    """宽度不足时以省略号显示，鼠标悬停可查看全文。"""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(0)
        self.setText(text)

    def setText(self, text):
        self._full_text = text or ""
        self.setToolTip(self._full_text)
        super().setText(self._full_text)

    def fullText(self):
        return self._full_text

    def paintEvent(self, event):
        painter = QPainter(self)
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(self._full_text, Qt.ElideMiddle, self.width())
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(self.contentsRect(), int(self.alignment()), elided)


class DropZone(QFrame):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class Toast(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignCenter)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text, kind="info", msec=4200):
        self._timer.stop()
        self.hide()
        self.setProperty("kind", kind)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.setText(text)
        parent = self.parentWidget()
        max_width = max(260, min(620, parent.width() - 60)) if parent else 520
        desired = self.fontMetrics().horizontalAdvance(text) + 44
        self.setWordWrap(True)
        self.setFixedWidth(max(240, min(max_width, desired)))
        self.adjustSize()
        self._reposition()
        self.raise_()
        self.show()
        self._timer.start(msec)

    def _reposition(self):
        parent = self.parentWidget()
        if not parent:
            return
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - 46
        self.move(max(16, x), max(16, y))


@dataclass
class SearchResult:
    path: str
    query: str
    pattern: str
    result_path: Optional[str]
    loaded: core.LoadedText
    char_count: int
    sentences: List[str]
    matched: List[int]
    source_stat: Tuple[int, int]
    timings: dict


class SearchWorker(QThread):
    phase = pyqtSignal(str)
    progress = pyqtSignal(int, int)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    canceled = pyqtSignal()

    def __init__(self, path, query, pattern, parent=None):
        super().__init__(parent)
        self._path = path
        self._query = query
        self._pattern = pattern
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def _is_canceled(self):
        return self._cancel_event.is_set()

    def run(self):
        timings = {}
        started = time.perf_counter()
        try:
            self.phase.emit("正在读取文件…")
            source_stat = os.stat(self._path)
            read_started = time.perf_counter()
            loaded = core.read_text(self._path)
            timings["read"] = time.perf_counter() - read_started
            if self._is_canceled():
                self.canceled.emit()
                return

            self.phase.emit("正在拆分句子…")
            split_started = time.perf_counter()
            boundary_re = core.compile_boundary(self._pattern)
            source_text = loaded.text
            char_count = len(source_text)
            sentences = core.split_sentences(source_text, boundary_re)
            del source_text
            timings["split"] = time.perf_counter() - split_started
            if self._is_canceled():
                self.canceled.emit()
                return

            total = len(sentences)
            self.progress.emit(0, total)
            self.phase.emit("正在比对广告句…")
            matcher = core.parse_query(self._query)
            matched = []
            match_started = time.perf_counter()
            for index, sentence in enumerate(sentences):
                if index % 20000 == 0:
                    if self._is_canceled():
                        self.canceled.emit()
                        return
                    self.progress.emit(index, total)
                if matcher(sentence):
                    matched.append(index)
            timings["match"] = time.perf_counter() - match_started
            self.progress.emit(total, total)
            if self._is_canceled():
                self.canceled.emit()
                return

            self.phase.emit("正在保存检索结果…")
            result_path = os.path.join(core.get_desktop_dir(), core.RESULT_FILE_NAME)
            write_started = time.perf_counter()
            core.write_result_file(
                result_path, [sentences[index] for index in matched]
            )
            timings["write"] = time.perf_counter() - write_started

            timings["total"] = time.perf_counter() - started
            loaded_meta = core.LoadedText(
                text="",
                encoding=loaded.encoding,
                newline=loaded.newline,
                size=loaded.size,
                had_bom=loaded.had_bom,
            )
            self.succeeded.emit(
                SearchResult(
                    path=self._path,
                    query=self._query,
                    pattern=self._pattern,
                    result_path=result_path,
                    loaded=loaded_meta,
                    char_count=char_count,
                    sentences=sentences,
                    matched=matched,
                    source_stat=(source_stat.st_size, source_stat.st_mtime_ns),
                    timings=timings,
                )
            )
        except Exception as exc:
            self.failed.emit(str(exc) or exc.__class__.__name__)


class BoundaryDialog(QDialog):
    def __init__(self, parent, current_pattern, default_pattern, colors, font_size=15):
        super().__init__(parent)
        self.setWindowTitle("编辑句子分隔符")
        self.setModal(True)
        self.resize(700, 600)
        self.setMinimumSize(600, 500)
        self._colors = colors
        self._font_size = font_size
        self._default_pattern = default_pattern
        self._pattern = None
        self._validate_timer = QTimer(self)
        self._validate_timer.setSingleShot(True)
        self._validate_timer.timeout.connect(self._validate)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("编辑句子分隔符")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        description = QLabel("用正则拆分句子；只写分隔符本身，程序会自动包裹捕获组。")
        description.setObjectName("Hint")
        description.setWordWrap(True)
        layout.addWidget(description)

        self.pattern_edit = QPlainTextEdit()
        self.pattern_edit.setPlainText(current_pattern)
        self.pattern_edit.setFixedHeight(112)
        self.pattern_edit.setToolTip("只填写分隔符正则，不需要 re.compile 包裹")
        layout.addWidget(self.pattern_edit)

        self.status_label = QLabel("")
        self.status_label.setObjectName("Hint")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        preview_label = QLabel("用当前正则拆分示例文本：")
        preview_label.setObjectName("FieldLabel")
        layout.addWidget(preview_label)

        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(False)
        layout.addWidget(self.preview, 1)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.reset_btn = QPushButton("恢复默认")
        self.reset_btn.setObjectName("Ghost")
        self.reset_btn.clicked.connect(self._reset)
        button_row.addWidget(self.reset_btn)
        button_row.addStretch(1)
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("Ghost")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        self.save_btn = QPushButton("保存并使用")
        self.save_btn.setObjectName("Primary")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save)
        button_row.addWidget(self.save_btn)
        layout.addLayout(button_row)

        self.pattern_edit.textChanged.connect(self._schedule_validate)
        self._validate()

    def _schedule_validate(self):
        self._validate_timer.start(180)

    def _validate(self):
        pattern = self.pattern_edit.toPlainText().strip()
        try:
            boundary_re = core.compile_boundary(pattern)
        except ValueError as exc:
            self._set_tone(self.status_label, "error")
            self.status_label.setText(str(exc))
            self.preview.setHtml(
                '<div style="color:%s; padding:8px;">%s</div>'
                % (self._colors["danger"], html.escape(str(exc)))
            )
            self.save_btn.setEnabled(False)
            return

        segments = core.split_sentences(SAMPLE_TEXT, boundary_re)
        self._set_tone(self.status_label, "success")
        self.status_label.setText(
            "正则有效，示例文本被拆成 %d 段。保存后需要重新检索。" % len(segments)
        )
        self.save_btn.setEnabled(True)

        rows = []
        for index, segment in enumerate(segments[:12], 1):
            text = segment.replace("\n", "⏎")
            if len(text) > 150:
                text = text[:150] + "…"
            rows.append(
                '<tr><td style="color:%s; padding:5px 10px 5px 0; vertical-align:top;">%d</td>'
                '<td style="padding:5px 0; color:%s;">%s</td></tr>'
                % (
                    self._colors["primary"],
                    index,
                    self._colors["text"],
                    html.escape(text) or "（空片段）",
                )
            )
        if len(segments) > 12:
            rows.append(
                '<tr><td></td><td style="padding:8px 0; color:%s;">仅预览前 12 段，共 %d 段。</td></tr>'
                % (self._colors["muted"], len(segments))
            )
        self.preview.setHtml(
            '<html><body style="background:transparent; font-family:Microsoft YaHei UI; '
            'font-size:%dpx;"><table cellspacing="0" cellpadding="0">%s</table></body></html>'
            % (max(11, int(round(12 * self._font_size / 13.0))), "".join(rows))
        )

    @staticmethod
    def _set_tone(widget, tone):
        widget.setProperty("tone", tone)
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()

    def _reset(self):
        self.pattern_edit.setPlainText(self._default_pattern)
        self.pattern_edit.setFocus()

    def _save(self):
        pattern = self.pattern_edit.toPlainText().strip()
        try:
            core.compile_boundary(pattern)
        except ValueError:
            self._schedule_validate()
            return
        self._pattern = pattern
        self.accept()

    def get_pattern(self):
        return self._pattern


class SettingsDialog(QDialog):
    def __init__(self, parent, presets, font_size, colors):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setModal(True)
        self.resize(760, 660)
        self.setMinimumSize(680, 560)
        self._colors = colors
        self._result_presets = [tuple(item) for item in presets]
        self._result_font_size = font_size

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        title = QLabel("设置")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        description = QLabel("常用规则用于快速填入检索词，字号只影响界面。")
        description.setObjectName("Hint")
        description.setWordWrap(True)
        layout.addWidget(description)

        preset_card = QFrame()
        preset_card.setObjectName("Card")
        preset_layout = QVBoxLayout(preset_card)
        preset_layout.setContentsMargins(14, 12, 14, 12)
        preset_layout.setSpacing(8)

        preset_title = QLabel("常用规则")
        preset_title.setObjectName("FieldLabel")
        preset_layout.addWidget(preset_title)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["名称", "检索式"])
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 150)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(
            max(34, int(font_size) + 16)
        )
        self.table.setAccessibleName("常用规则列表")
        self.table.setMinimumHeight(250)
        preset_layout.addWidget(self.table, 1)

        table_actions = QHBoxLayout()
        table_actions.setSpacing(8)
        add_btn = QPushButton("新增")
        add_btn.setObjectName("Ghost")
        add_btn.clicked.connect(self._add_row)
        table_actions.addWidget(add_btn)
        remove_btn = QPushButton("删除")
        remove_btn.setObjectName("Ghost")
        remove_btn.clicked.connect(self._remove_rows)
        table_actions.addWidget(remove_btn)
        restore_btn = QPushButton("恢复默认")
        restore_btn.setObjectName("Ghost")
        restore_btn.clicked.connect(self._restore_defaults)
        table_actions.addWidget(restore_btn)
        table_actions.addStretch(1)
        preset_layout.addLayout(table_actions)
        layout.addWidget(preset_card, 1)

        font_card = QFrame()
        font_card.setObjectName("Card")
        font_layout = QVBoxLayout(font_card)
        font_layout.setContentsMargins(14, 12, 14, 12)
        font_layout.setSpacing(8)

        font_title = QLabel("界面字号")
        font_title.setObjectName("FieldLabel")
        font_layout.addWidget(font_title)

        font_row = QHBoxLayout()
        font_row.setSpacing(10)
        self.font_spin = QSpinBox()
        self.font_spin.setRange(MIN_FONT_SIZE, MAX_FONT_SIZE)
        self.font_spin.setValue(font_size)
        self.font_spin.setSuffix(" px")
        self.font_spin.setMinimumWidth(110)
        self.font_spin.setAccessibleName("界面字号")
        self.font_spin.valueChanged.connect(self._update_preview)
        font_row.addWidget(self.font_spin)
        family = QLabel("字体固定为 %s" % FONT_FAMILY)
        family.setObjectName("Hint")
        font_row.addWidget(family)
        font_row.addStretch(1)
        font_layout.addLayout(font_row)

        self.font_preview = QLabel("网址 OR 公众号 AND 关注")
        self.font_preview.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.font_preview.setMinimumHeight(42)
        font_layout.addWidget(self.font_preview)
        layout.addWidget(font_card)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("Ghost")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        save_btn = QPushButton("保存")
        save_btn.setObjectName("Primary")
        save_btn.clicked.connect(self._save)
        button_row.addWidget(save_btn)
        layout.addLayout(button_row)

        self._set_rows(presets)
        self._update_preview(font_size)

    def _set_rows(self, rows):
        self.table.setRowCount(0)
        for name, query in rows:
            self._append_row(name, query)
        if self.table.rowCount() == 0:
            self._append_row("", "")

    def _append_row(self, name, query):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(name)))
        self.table.setItem(row, 1, QTableWidgetItem(str(query)))
        self.table.setCurrentCell(row, 0)

    def _add_row(self):
        self._append_row("", "")
        self.table.editItem(self.table.item(self.table.rowCount() - 1, 0))

    def _remove_rows(self):
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "删除规则", "请先选择要删除的行。")
            return
        for row in rows:
            self.table.removeRow(row)
        if self.table.rowCount() == 0:
            self._append_row("", "")

    def _restore_defaults(self):
        self._set_rows(QUERY_PRESETS)

    def _update_preview(self, value):
        self.font_preview.setStyleSheet(
            "font-size:%dpx; color:%s; background:%s; border:1px solid %s;"
            " border-radius:8px; padding:8px 12px;"
            % (int(value), self._colors["text"], self._colors["surface_alt"],
               self._colors["border"])
        )

    def _collect(self):
        presets = []
        names = set()
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            query_item = self.table.item(row, 1)
            name = name_item.text().strip() if name_item else ""
            query = query_item.text().strip() if query_item else ""
            if not name and not query:
                continue
            if not name or not query:
                QMessageBox.warning(self, "规则不完整", "每行的名称和检索式都需要填写。")
                return None
            if name in names:
                QMessageBox.warning(self, "名称重复", "规则名称不能重复：%s" % name)
                return None
            names.add(name)
            presets.append((name, query))
        return presets

    def _save(self):
        presets = self._collect()
        if presets is None:
            return
        self._result_presets = presets
        self._result_font_size = self.font_spin.value()
        self.accept()

    def result_presets(self):
        return list(self._result_presets)

    def result_font_size(self):
        return self._result_font_size


class HelpDialog(QDialog):
    def __init__(self, parent, colors, font_size=15):
        super().__init__(parent)
        self.setWindowTitle("使用说明")
        self.setModal(True)
        self.resize(760, 620)
        self.setMinimumSize(640, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(self._build_html(colors, font_size))
        layout.addWidget(browser, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        close_btn = QPushButton("开始使用")
        close_btn.setObjectName("Primary")
        close_btn.clicked.connect(self.accept)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

    @staticmethod
    def _build_html(colors, font_size=15):
        scale = font_size / 13.0
        heading_size = max(22, int(round(24 * scale)))
        section_size = max(16, int(round(17 * scale)))
        return """
        <html><head><style>
        body {{ font-family: "Microsoft YaHei UI"; color: {text}; font-size: {body_size}px; }}
        h1 {{ font-size: {heading_size}px; color: {text}; margin: 0 0 6px 0; }}
        h2 {{ font-size: {section_size}px; color: {primary}; margin: 20px 0 6px 0; }}
        p {{ margin: 6px 0; }}
        li {{ margin: 4px 0; }}
        code {{ background-color: {code_bg}; color: {primary}; padding: 1px 5px; }}
        table {{ border-collapse: collapse; }}
        td {{ padding: 4px 16px 4px 0; color: {text}; }}
        .muted {{ color: {muted}; }}
        </style></head><body>
        <h1>小说广告清理工具</h1>
        <p class="muted">版本 {version} · 所有处理都在本机完成，文件不会上传。</p>

        <h2>四步完成清理</h2>
        <ol>
          <li><b>选择小说</b>：拖入或选择一个 .txt 文件。程序会自动识别 UTF-8、GBK、GB18030，并尽力识别 Big5 与带 BOM 的 UTF-16。</li>
          <li><b>输入检索词</b>：填写广告中稳定出现的字样，点击“检索”。大型文件会显示进度，可随时取消。</li>
          <li><b>复核结果</b>：检索完成后，桌面会生成 <code>检索结果.txt</code>。用记事本打开，删除不想清理的行并保存。序号是删除依据，改句子文字不影响结果。</li>
          <li><b>删除广告</b>：设置输出目录与编码，点击“删除广告并保存”。程序只生成副本，原文件不会改动。</li>
        </ol>

        <h2>检索语法</h2>
        <ul>
          <li><code>网址 OR 公众号</code>：句子包含任意一个关键词即命中。</li>
          <li><code>网址 AND 广告</code>：同一句必须同时包含两个关键词。</li>
          <li><code>A AND B OR C</code>：理解为（A 且 B）或 C。</li>
          <li class="muted">AND / OR 必须大写；关键词区分大小写，按普通子串匹配，不支持通配符。</li>
        </ul>

        <h2>输出与安全</h2>
        <ul>
          <li>输出文件名为 <code>原文件名去广告.txt</code>。若原文件名已含“去广告”，会追加 <code>_clean</code>，避免覆盖源文件。</li>
          <li>默认输出 UTF-8（带 BOM），也可跟随原文件编码；原换行风格会保留。</li>
          <li>写入采用临时文件替换，失败时不会留下半截文件。</li>
          <li>保存前会再次确认；目标文件已存在时会单独询问是否覆盖。</li>
          <li>若源文件在检索后被修改，程序会拒绝删除并要求重新检索。</li>
        </ul>

        <h2>常用快捷键</h2>
        <table>
          <tr><td><code>Ctrl+O</code></td><td>选择小说</td></tr>
          <tr><td><code>Ctrl+F</code></td><td>聚焦检索词</td></tr>
          <tr><td><code>F5</code> / <code>Ctrl+Enter</code></td><td>开始检索</td></tr>
          <tr><td><code>Ctrl+D</code></td><td>删除广告并保存</td></tr>
          <tr><td><code>Ctrl+E</code></td><td>编辑句子分隔符</td></tr>
          <tr><td><code>F1</code></td><td>打开使用说明</td></tr>
          <tr><td><code>Esc</code></td><td>取消正在进行的检索</td></tr>
        </table>

        <h2>遇到问题</h2>
        <ul>
          <li><b>编码无法识别</b>：用记事本或 VS Code 将文件另存为 UTF-8 后重试。</li>
          <li><b>没有命中</b>：换更短、更稳定的词，例如 <code>http</code>、<code>公众号</code>，不要输入整句广告。</li>
          <li><b>检索结果文件不见了</b>：重新检索一次；删除动作依赖本次检索生成的结果文件。</li>
          <li><b>想恢复默认分隔符</b>：在“分隔符”对话框点击“恢复默认”。</li>
        </ul>
        <p class="muted">设置保存在 <code>%APPDATA%\\TXTAdCleaner\\settings.ini</code>，可随时删除以恢复默认。</p>
        </body></html>
        """.format(
            version=APP_VERSION,
            body_size=font_size,
            heading_size=heading_size,
            section_size=section_size,
            **colors
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("%s v%s" % (APP_NAME, APP_VERSION))
        self.setAcceptDrops(True)
        self.setMinimumSize(980, 640)
        self._icon = build_app_icon()
        self.setWindowIcon(self._icon)

        self._settings = QSettings(_settings_path(), QSettings.IniFormat)
        self._settings.setFallbacksEnabled(False)
        self._history = self._load_history()
        self._presets = self._load_presets()
        self._font_size = self._load_font_size()
        self._restore_warning = None
        self._boundary_pattern = self._load_boundary_pattern()
        self.boundary_re = core.compile_boundary(self._boundary_pattern)
        saved_theme = str(self._settings.value("theme", "") or "")
        self.current_theme = (
            saved_theme
            if saved_theme in THEMES
            else ("dark" if _system_prefers_dark() else "light")
        )
        self._colors = THEMES[self.current_theme]
        self._cards = []

        self.source_path = None
        self.loaded = None
        self.sentences = None
        self.index_map = None
        self.matched = None
        self.result_path = None
        self.source_stat = None
        self._deletion_cache_valid = False
        self._last_output = None
        self._last_output_dir = None
        self._worker = None
        self._search_started = 0.0
        self._empty_action_mode = "file"

        self._build_ui()
        self._apply_theme(self.current_theme, persist=False)
        self._restore_window_state()
        self._load_preferences_into_ui()

        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(200)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)

        self._progress_hide_timer = QTimer(self)
        self._progress_hide_timer.setSingleShot(True)
        self._progress_hide_timer.timeout.connect(self.progress_bar.hide)

        self._toast = Toast(self._root)
        self._install_shortcuts()
        self._update_output_preview()
        self._update_boundary_hint()
        self._log("就绪。选择小说后，输入广告特征词开始检索。")
        self._log("所有文本处理均在本机完成，文件不会上传。")
        if self._restore_warning:
            self._log(self._restore_warning)
        QTimer.singleShot(0, self._apply_dark_title_bar)

    # ---------------------------------------------------------------- 设置
    def _load_history(self):
        value = self._settings.value("query_history", [])
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return []
        history = []
        for item in value:
            text = str(item).strip()
            if text and text not in history:
                history.append(text)
        return history[:10]

    def _load_boundary_pattern(self):
        value = self._settings.value(
            "boundary_pattern", core.DEFAULT_BOUNDARY_PATTERN, type=str
        )
        pattern = (value or "").strip() or core.DEFAULT_BOUNDARY_PATTERN
        try:
            core.compile_boundary(pattern)
        except ValueError as exc:
            self._restore_warning = "已恢复默认分隔符：保存的自定义正则无效（%s）。" % exc
            return core.DEFAULT_BOUNDARY_PATTERN
        return pattern

    def _load_presets(self):
        raw = self._settings.value("query_presets", "")
        if not raw:
            return list(QUERY_PRESETS)
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            return list(QUERY_PRESETS)
        if not isinstance(data, list):
            return list(QUERY_PRESETS)
        presets = []
        for item in data:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                name, query = str(item[0]).strip(), str(item[1]).strip()
                if name and query:
                    presets.append((name, query))
        return presets

    def _load_font_size(self):
        value = self._settings.value("font_size", DEFAULT_FONT_SIZE)
        try:
            size = int(value)
        except (TypeError, ValueError):
            size = DEFAULT_FONT_SIZE
        return max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))

    def _left_width(self):
        return 430 + max(0, self._font_size - 15) * 12

    def _font_tokens(self):
        base = self._font_size
        scale = base / float(BASE_FONT_SIZE)

        def scaled(value, minimum=10):
            return max(minimum, int(round(value * scale)))

        def px(value):
            return "%dpx" % value

        return {
            "fs_base": px(base),
            "fs_title": px(scaled(24, 20)),
            "fs_small": px(scaled(11, 10)),
            "fs_section": px(scaled(15, 13)),
            "fs_meta": px(scaled(12, 11)),
            "fs_panel": px(scaled(16, 14)),
            "fs_status": px(scaled(12, 11)),
            "fs_empty_icon": px(scaled(18, 16)),
            "fs_file": px(scaled(14, 12)),
            "fs_danger": px(scaled(14, 12)),
            "fs_log": px(scaled(12, 11)),
            "fs_row_height": px(base + 13),
        }

    def _restore_window_state(self):
        geometry = self._settings.value("geometry")
        restored = False
        if geometry is not None:
            try:
                restored = bool(self.restoreGeometry(geometry))
            except Exception:
                restored = False
        if not restored:
            available = QApplication.primaryScreen().availableGeometry()
            width = max(980, min(1180, int(available.width() * 0.92)))
            height = max(640, min(780, int(available.height() * 0.92)))
            self.resize(width, height)
            frame = self.frameGeometry()
            frame.moveCenter(available.center())
            self.move(frame.topLeft())
        else:
            frame = self.frameGeometry()
            if not any(
                screen.availableGeometry().intersects(frame)
                for screen in QApplication.screens()
            ):
                available = QApplication.primaryScreen().availableGeometry()
                frame.moveCenter(available.center())
                self.move(frame.topLeft())

    def _load_preferences_into_ui(self):
        self._populate_history("")
        index = self._settings.value("encoding_index", 0)
        try:
            index = int(index)
        except (TypeError, ValueError):
            index = 0
        if 0 <= index < self.encoding_combo.count():
            self.encoding_combo.setCurrentIndex(index)

    def _save_settings(self):
        try:
            self._settings.setValue("theme", self.current_theme)
            self._settings.setValue("geometry", self.saveGeometry())
            self._settings.setValue("query_history", self._history[:10])
            self._settings.setValue("encoding_index", self.encoding_combo.currentIndex())
            self._settings.setValue("boundary_pattern", self._boundary_pattern)
            self._settings.setValue("font_size", self._font_size)
            self._settings.setValue(
                "query_presets",
                json.dumps(self._presets, ensure_ascii=False),
            )
            self._settings.setValue(
                "last_dir",
                os.path.dirname(self.source_path) if self.source_path else "",
            )
            self._settings.sync()
        except Exception:
            pass

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QWidget()
        root.setObjectName("Root")
        self._root = root
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(22, 16, 22, 10)
        root_layout.setSpacing(12)

        root_layout.addWidget(self._build_header())

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(16)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setFixedWidth(self._left_width())
        left_scroll.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.left_scroll = left_scroll

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(6, 6, 10, 6)
        left_layout.setSpacing(10)
        left_layout.addWidget(self._build_file_card())
        left_layout.addWidget(self._build_rule_card())
        left_layout.addWidget(self._build_save_card())
        left_layout.addStretch(1)
        left_scroll.setWidget(left_panel)

        body_layout.addWidget(left_scroll)
        body_layout.addWidget(self._build_result_card(), 1)
        root_layout.addWidget(body, 1)

        divider = QFrame()
        divider.setObjectName("Divider")
        root_layout.addWidget(divider)

        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(2, 0, 2, 0)
        footer_layout.setSpacing(8)
        self.footer_status = QLabel("● 就绪")
        self.footer_status.setObjectName("FooterStatus")
        footer_layout.addWidget(self.footer_status)
        footer_layout.addStretch(1)
        footer_meta = QLabel("本地处理 · 文件不会上传 · v%s" % APP_VERSION)
        footer_meta.setObjectName("Hint")
        footer_layout.addWidget(footer_meta)
        root_layout.addWidget(footer)

        self.setCentralWidget(root)

    def _build_header(self):
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(12)

        logo = QLabel()
        logo.setPixmap(self._icon.pixmap(50, 50))
        logo.setFixedSize(50, 50)
        logo.setToolTip(APP_NAME)
        shadow = QGraphicsDropShadowEffect(logo)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(37, 99, 235, 60))
        logo.setGraphicsEffect(shadow)
        layout.addWidget(logo)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title = QLabel(APP_NAME)
        title.setObjectName("Title")
        title_row.addWidget(title)
        version = QLabel("v%s" % APP_VERSION)
        version.setObjectName("Version")
        title_row.addWidget(version, 0, Qt.AlignVCenter)
        title_row.addStretch(1)
        title_box.addLayout(title_row)

        subtitle = QLabel("定位并清理 TXT 小说里的广告句")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(subtitle)
        layout.addLayout(title_box, 1)

        self.theme_btn = QPushButton("深色模式")
        self.theme_btn.setObjectName("Ghost")
        self.theme_btn.setMinimumHeight(34)
        self.theme_btn.setMinimumWidth(94)
        self.theme_btn.setToolTip("切换浅色 / 深色主题")
        self.theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_btn)

        help_btn = QPushButton("使用说明")
        help_btn.setObjectName("Ghost")
        help_btn.setMinimumHeight(34)
        help_btn.setMinimumWidth(88)
        help_btn.setToolTip("查看完整说明（F1）")
        help_btn.clicked.connect(self.show_help)
        layout.addWidget(help_btn)

        self.settings_btn = QPushButton("设置")
        self.settings_btn.setObjectName("Ghost")
        self.settings_btn.setMinimumHeight(34)
        self.settings_btn.setMinimumWidth(64)
        self.settings_btn.setToolTip("编辑常用规则与字号（Ctrl+,）")
        self.settings_btn.clicked.connect(self.show_settings)
        layout.addWidget(self.settings_btn)
        return header

    def _make_card(self, number, title, subtitle):
        card = QFrame()
        card.setObjectName("Card")
        self._cards.append(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(10)
        number_label = QLabel(str(number))
        number_label.setObjectName("Number")
        number_label.setFixedSize(26, 26)
        number_label.setAlignment(Qt.AlignCenter)
        head.addWidget(number_label, 0, Qt.AlignTop)

        text_box = QVBoxLayout()
        text_box.setSpacing(0)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("SectionSub")
        subtitle_label.setWordWrap(True)
        text_box.addWidget(title_label)
        text_box.addWidget(subtitle_label)
        head.addLayout(text_box, 1)
        layout.addLayout(head)
        return card, layout

    def _build_file_card(self):
        card, layout = self._make_card(
            1, "选择小说", "拖入或选择 .txt 文件"
        )

        self.drop_zone = DropZone()
        self.drop_zone.setObjectName("DropZone")
        self.drop_zone.setMinimumHeight(76)
        self.drop_zone.setCursor(Qt.PointingHandCursor)
        self.drop_zone.setToolTip("点击选择 TXT 文件，或直接把文件拖进窗口")
        self.drop_zone.clicked.connect(self.choose_file)
        drop_layout = QHBoxLayout(self.drop_zone)
        drop_layout.setContentsMargins(12, 10, 12, 10)
        drop_layout.setSpacing(10)

        glyph = QLabel("TXT")
        glyph.setObjectName("FileGlyph")
        glyph.setFixedSize(44, 48)
        glyph.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(glyph)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        self.file_name_label = ElidedLabel("尚未选择小说")
        self.file_name_label.setObjectName("FileName")
        self.file_path_label = ElidedLabel("拖入或点击此处选择文件")
        self.file_path_label.setObjectName("Hint")
        text_box.addWidget(self.file_name_label)
        text_box.addWidget(self.file_path_label)
        drop_layout.addLayout(text_box, 1)

        self.browse_btn = QPushButton("选择文件")
        self.browse_btn.setObjectName("Ghost")
        self.browse_btn.setMinimumHeight(34)
        self.browse_btn.setToolTip("选择 TXT 文件（Ctrl+O）")
        self.browse_btn.clicked.connect(self.choose_file)
        drop_layout.addWidget(self.browse_btn, 0, Qt.AlignVCenter)
        layout.addWidget(self.drop_zone)

        self.meta_label = ElidedLabel("大小 —  ·  编码 —  ·  字符 —  ·  句子 —")
        self.meta_label.setObjectName("Hint")
        layout.addWidget(self.meta_label)
        return card

    def _build_rule_card(self):
        card, layout = self._make_card(
            2, "设置检索规则", "AND 同时包含 · OR 任一满足"
        )

        self.query_combo = QComboBox()
        self.query_combo.setEditable(True)
        self.query_combo.setInsertPolicy(QComboBox.NoInsert)
        self.query_combo.setMaxVisibleItems(12)
        self.query_combo.setMinimumHeight(38)
        self.query_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLength)
        self.query_combo.setMinimumContentsLength(8)
        self.query_combo.lineEdit().setPlaceholderText(
            "例如：网址 OR 公众号 AND 关注"
        )
        self.query_combo.lineEdit().setClearButtonEnabled(True)
        self.query_combo.lineEdit().returnPressed.connect(self.start_search)
        self.query_combo.lineEdit().textChanged.connect(self._on_query_changed)
        self.query_combo.setAccessibleName("检索词")
        if self.query_combo.completer() is not None:
            self.query_combo.completer().setFilterMode(Qt.MatchContains)
            self.query_combo.completer().setCaseSensitivity(Qt.CaseInsensitive)
        layout.addWidget(self.query_combo)

        self.query_warning = QLabel(
            "检测到小写 and / or：操作符需要大写，否则会被当作普通关键词。"
        )
        self.query_warning.setObjectName("Hint")
        self.query_warning.setProperty("tone", "error")
        self.query_warning.setWordWrap(True)
        self.query_warning.hide()
        layout.addWidget(self.query_warning)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.search_btn = QPushButton("检索")
        self.search_btn.setObjectName("Primary")
        self.search_btn.setMinimumHeight(38)
        self.search_btn.setToolTip("开始检索（F5 / Ctrl+Enter）")
        self.search_btn.clicked.connect(self.start_search)
        button_row.addWidget(self.search_btn, 1)

        self.preset_btn = QPushButton("常用规则")
        self.preset_btn.setObjectName("Ghost")
        self.preset_btn.setMinimumHeight(38)
        self.preset_menu = QMenu(self)
        self.preset_btn.setMenu(self.preset_menu)
        self._rebuild_preset_menu()
        self.preset_btn.setToolTip("填入常见的广告检索词")
        button_row.addWidget(self.preset_btn)

        self.boundary_btn = QPushButton("分隔符")
        self.boundary_btn.setObjectName("Ghost")
        self.boundary_btn.setMinimumHeight(38)
        self.boundary_btn.setMinimumWidth(78)
        self.boundary_btn.setToolTip("编辑句子分隔符（Ctrl+E）")
        self.boundary_btn.clicked.connect(self.edit_boundary)
        button_row.addWidget(self.boundary_btn)
        layout.addLayout(button_row)

        hint = QLabel("示例：网址 OR 公众号 AND 关注")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return card

    def _build_save_card(self):
        card, layout = self._make_card(
            3, "清理并保存", "生成去广告副本，原文件不改动"
        )

        output_row = QHBoxLayout()
        output_row.setSpacing(8)
        self.output_edit = QLineEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setMinimumHeight(36)
        self.output_edit.setPlaceholderText("输出目录")
        self.output_edit.setToolTip("清理后的副本保存到这里")
        output_row.addWidget(self.output_edit, 1)
        self.output_btn = QPushButton("更改")
        self.output_btn.setObjectName("Ghost")
        self.output_btn.setMinimumHeight(36)
        self.output_btn.setMinimumWidth(58)
        self.output_btn.clicked.connect(self.choose_output_dir)
        output_row.addWidget(self.output_btn)
        layout.addLayout(output_row)

        self.output_preview = ElidedLabel("输出文件：选择小说后自动填充")
        self.output_preview.setObjectName("Hint")
        layout.addWidget(self.output_preview)

        encoding_row = QHBoxLayout()
        encoding_row.setSpacing(8)
        encoding_label = QLabel("编码")
        encoding_label.setObjectName("FieldLabel")
        encoding_row.addWidget(encoding_label)
        self.encoding_combo = QComboBox()
        self.encoding_combo.setMinimumHeight(34)
        for label, value in OUTPUT_ENCODINGS:
            self.encoding_combo.addItem(label, value)
        self.encoding_combo.setToolTip("选择输出文件编码；默认 UTF-8 带 BOM")
        encoding_row.addWidget(self.encoding_combo, 1)
        layout.addLayout(encoding_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.delete_btn = QPushButton("删除广告并保存")
        self.delete_btn.setObjectName("Danger")
        self.delete_btn.setMinimumHeight(40)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setToolTip("按检索结果文件中的序号删除，并保存副本（Ctrl+D）")
        self.delete_btn.clicked.connect(self.delete_ads)
        action_row.addWidget(self.delete_btn, 1)

        self.open_output_btn = QPushButton("打开目录")
        self.open_output_btn.setObjectName("Ghost")
        self.open_output_btn.setMinimumHeight(40)
        self.open_output_btn.setMinimumWidth(84)
        self.open_output_btn.setEnabled(False)
        self.open_output_btn.setToolTip("打开保存清理结果的文件夹")
        self.open_output_btn.clicked.connect(self.open_output_dir)
        action_row.addWidget(self.open_output_btn)
        layout.addLayout(action_row)

        safety = QLabel("原文件只读，另存副本")
        safety.setObjectName("Hint")
        safety.setWordWrap(True)
        layout.addWidget(safety)
        return card

    def _build_result_card(self):
        card = QFrame()
        card.setObjectName("Card")
        self._cards.append(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 12)
        layout.setSpacing(9)

        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("检索结果")
        title.setObjectName("PanelTitle")
        head.addWidget(title)
        self.count_badge = QLabel("0 条命中")
        self.count_badge.setObjectName("Badge")
        head.addWidget(self.count_badge)
        head.addStretch(1)
        self.open_result_btn = QPushButton("打开结果文件")
        self.open_result_btn.setObjectName("Ghost")
        self.open_result_btn.setMinimumHeight(30)
        self.open_result_btn.setEnabled(False)
        self.open_result_btn.setToolTip("打开桌面上的“检索结果.txt”，删除前可手动编辑")
        self.open_result_btn.clicked.connect(self.open_result_file)
        head.addWidget(self.open_result_btn)
        layout.addLayout(head)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        preview_page = QWidget()
        preview_layout = QVBoxLayout(preview_page)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_stack = QStackedWidget()

        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.setContentsMargins(20, 24, 20, 24)
        empty_layout.setSpacing(8)
        empty_layout.addStretch(1)
        self.empty_icon = QLabel("TXT")
        self.empty_icon.setObjectName("EmptyIcon")
        self.empty_icon.setFixedSize(64, 64)
        self.empty_icon.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(self.empty_icon, 0, Qt.AlignHCenter)
        self.empty_title = QLabel("还没有检索结果")
        self.empty_title.setObjectName("EmptyTitle")
        self.empty_title.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(self.empty_title)
        self.empty_sub = QLabel("选择小说并输入检索词，结果会显示在这里。")
        self.empty_sub.setObjectName("Hint")
        self.empty_sub.setAlignment(Qt.AlignCenter)
        self.empty_sub.setWordWrap(True)
        self.empty_sub.setFixedWidth(360)
        self.empty_sub.setMinimumHeight(42)
        empty_layout.addWidget(self.empty_sub, 0, Qt.AlignHCenter)
        self.empty_action = QPushButton("选择小说")
        self.empty_action.setObjectName("Ghost")
        self.empty_action.setFixedWidth(120)
        self.empty_action.clicked.connect(self._on_empty_action)
        empty_layout.addWidget(self.empty_action, 0, Qt.AlignHCenter)
        empty_layout.addStretch(1)

        self.preview = QTextBrowser()
        self.preview.setObjectName("Preview")
        self.preview.setOpenExternalLinks(False)
        self.preview.setFrameShape(QFrame.NoFrame)
        self.preview.setAccessibleName("命中句预览")

        self.preview_stack.addWidget(empty_page)
        self.preview_stack.addWidget(self.preview)
        preview_layout.addWidget(self.preview_stack)
        self.tabs.addTab(preview_page, "命中预览")

        log_page = QWidget()
        log_layout = QVBoxLayout(log_page)
        log_layout.setContentsMargins(0, 4, 0, 0)
        log_layout.setSpacing(4)
        log_head = QHBoxLayout()
        log_head.addStretch(1)
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.setObjectName("Link")
        clear_log_btn.clicked.connect(self._clear_log)
        log_head.addWidget(clear_log_btn)
        log_layout.addLayout(log_head)
        self.log_edit = QPlainTextEdit()
        self.log_edit.setObjectName("Log")
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumBlockCount(2000)
        self.log_edit.setPlaceholderText("运行日志会显示在这里")
        self.log_edit.setAccessibleName("运行日志")
        log_layout.addWidget(self.log_edit, 1)
        self.tabs.addTab(log_page, "运行日志")
        layout.addWidget(self.tabs, 1)

        self.result_hint = ElidedLabel("检索完成后生成 检索结果.txt")
        self.result_hint.setObjectName("Hint")
        layout.addWidget(self.result_hint)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self.status_label = QLabel("就绪，等待选择小说")
        self.status_label.setObjectName("ResultStatus")
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)
        self.elapsed_label = QLabel("")
        self.elapsed_label.setObjectName("Elapsed")
        status_row.addWidget(self.elapsed_label)
        layout.addLayout(status_row)
        return card

    # ------------------------------------------------------------- 主题/设置
    def _toggle_theme(self):
        self._apply_theme(
            "dark" if self.current_theme == "light" else "light", persist=True
        )

    def _apply_theme(self, name, persist=True):
        if name not in THEMES:
            name = "light"
        self.current_theme = name
        self._colors = THEMES[name]
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(
                QSS_TEMPLATE.substitute(**self._colors, **self._font_tokens())
            )
        self.theme_btn.setText("浅色模式" if name == "dark" else "深色模式")
        self.theme_btn.setToolTip(
            "切换到浅色主题" if name == "dark" else "切换到深色主题"
        )
        self._refresh_shadows()
        if hasattr(self, "left_scroll"):
            self.left_scroll.setFixedWidth(self._left_width())
        if self.matched:
            self._render_preview()
        if persist:
            self._settings.setValue("theme", name)
            self._settings.sync()
        self._apply_dark_title_bar()

    def _refresh_shadows(self):
        dark = self.current_theme == "dark"
        color = QColor(0, 0, 0, 120 if dark else 26)
        for card in self._cards:
            effect = QGraphicsDropShadowEffect(card)
            effect.setBlurRadius(34 if dark else 26)
            effect.setOffset(0, 7)
            effect.setColor(color)
            card.setGraphicsEffect(effect)

    def _apply_dark_title_bar(self):
        if sys.platform != "win32" or not self.isVisible():
            return
        try:
            hwnd = ctypes.c_void_p(int(self.winId()))
            value = ctypes.c_int(1 if self.current_theme == "dark" else 0)
            dwmapi = ctypes.windll.dwmapi
            dwmapi.DwmSetWindowAttribute.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_void_p,
                ctypes.c_uint,
            ]
            dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long
            for attribute in (20, 19):
                result = dwmapi.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
                )
                if result == 0:
                    break
        except Exception:
            pass

    # -------------------------------------------------------------- 快捷键
    def _install_shortcuts(self):
        shortcuts = [
            ("Ctrl+O", self.choose_file),
            ("Ctrl+F", self._focus_query),
            ("F5", self.start_search),
            ("Ctrl+Enter", self.start_search),
            ("Ctrl+D", self.delete_ads),
            ("Ctrl+E", self.edit_boundary),
            ("Ctrl+,", self.show_settings),
            ("F1", self.show_help),
            ("Esc", self._escape),
        ]
        for sequence, handler in shortcuts:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(handler)

    def _focus_query(self):
        self.query_combo.setFocus()
        self.query_combo.lineEdit().selectAll()

    def _escape(self):
        if self._worker is not None and self._worker.isRunning():
            self.cancel_search()

    # ---------------------------------------------------------------- 文件
    def choose_file(self):
        if self._worker is not None and self._worker.isRunning():
            return
        start_dir = self._settings.value("last_dir", "") or ""
        if not os.path.isdir(start_dir):
            start_dir = os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择小说 TXT",
            start_dir,
            "TXT 文件 (*.txt);;所有文件 (*.*)",
        )
        if path:
            self.select_file(path)

    def select_file(self, path):
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.warning(self, "请稍候", "检索正在进行，请先等待完成或取消检索。")
            return
        path = os.path.abspath(path)
        if not core.is_txt_file(path):
            QMessageBox.warning(self, "文件格式", "请选择 .txt 格式的小说文件。")
            return
        if not os.path.isfile(path):
            QMessageBox.critical(self, "文件不存在", "找不到文件：\n%s" % path)
            return
        try:
            size = os.path.getsize(path)
        except OSError as exc:
            QMessageBox.critical(self, "读取失败", "无法读取文件信息：\n%s" % exc)
            return
        if size == 0:
            QMessageBox.warning(self, "空文件", "这个文件是空的，请选择其他文件。")
            return

        self._clear_result_state()
        self.source_path = path
        self.loaded = None
        self._last_output = None
        self._last_output_dir = None
        name = os.path.basename(path)
        self.file_name_label.setText(name)
        self.file_path_label.setText(path)
        self.meta_label.setText(
            "大小 %s  ·  编码待检索  ·  字符 —  ·  句子 —"
            % core.format_size(size)
        )
        self.meta_label.setToolTip(path)

        self.output_edit.setText(os.path.dirname(path))
        self.output_edit.setCursorPosition(0)
        self._update_output_preview()
        self.open_output_btn.setEnabled(True)
        self._settings.setValue("last_dir", os.path.dirname(path))
        self._status("已选择小说，输入检索词后开始检索。")
        self._footer("● 已选择小说")
        self._log("已选择文件：%s（%s）" % (path, core.format_size(size)))
        self.query_combo.setFocus()

    def choose_output_dir(self):
        if self._worker is not None and self._worker.isRunning():
            return
        start_dir = self.output_edit.text().strip()
        if not os.path.isdir(start_dir):
            start_dir = (
                os.path.dirname(self.source_path) if self.source_path else os.path.expanduser("~")
            )
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录", start_dir)
        if directory:
            self.output_edit.setText(directory)
            self.output_edit.setCursorPosition(0)
            self._last_output_dir = None
            self._update_output_preview()
            self.open_output_btn.setEnabled(True)
            self._log("输出目录已更改为：%s" % directory)

    def _update_output_preview(self):
        if not self.source_path:
            self.output_preview.setText("输出文件：选择小说后自动填充")
            self.output_preview.setToolTip("")
            self._set_label_tone(self.output_preview, "")
            return
        output_dir = self.output_edit.text().strip()
        if not output_dir:
            self.output_preview.setText("输出文件：请选择输出目录")
            self.output_preview.setToolTip("")
            self._set_label_tone(self.output_preview, "")
            return
        out_path = core.make_output_path(self.source_path, output_dir)
        self.output_preview.setText("输出文件：%s" % os.path.basename(out_path))
        self.output_preview.setToolTip(out_path)
        if core.is_same_file(out_path, self.source_path):
            self.output_preview.setText("输出文件与源文件相同，请更改输出目录")
            self._set_label_tone(self.output_preview, "error")
        else:
            self._set_label_tone(self.output_preview, "")

    @staticmethod
    def _set_label_tone(label, tone):
        label.setProperty("tone", tone)
        style = label.style()
        style.unpolish(label)
        style.polish(label)
        label.update()

    # ---------------------------------------------------------------- 检索
    def _on_query_changed(self, text):
        self.query_warning.setVisible(core.has_lowercase_boolean_operator(text))

    def _apply_preset(self, name, query):
        self.query_combo.setEditText(query)
        self.query_combo.setFocus()
        self._log("已填入常用规则：%s" % name)

    def _remember_query(self, query):
        if not query:
            return
        self._history = [query] + [item for item in self._history if item != query]
        self._history = self._history[:10]
        self._populate_history(query)
        self._settings.setValue("query_history", self._history)
        self._settings.sync()

    def _populate_history(self, current_text):
        self.query_combo.blockSignals(True)
        self.query_combo.clear()
        self.query_combo.addItems(self._history)
        self.query_combo.setEditText(current_text or "")
        self.query_combo.blockSignals(False)

    def start_search(self):
        if self._worker is not None and self._worker.isRunning():
            self.cancel_search()
            return
        if not self.source_path:
            QMessageBox.warning(self, "请选择小说", "请先选择一个 .txt 小说文件。")
            return
        if not os.path.isfile(self.source_path):
            QMessageBox.critical(
                self, "文件不存在", "源文件已被移动或删除：\n%s" % self.source_path
            )
            return
        query = self.query_combo.currentText().strip()
        if not query:
            QMessageBox.warning(self, "缺少检索词", "请输入广告中稳定出现的词。")
            self.query_combo.setFocus()
            return
        if not core.parse_query_groups(query):
            QMessageBox.warning(
                self, "检索词无效", "请至少输入一个有效关键词，而不是只有 AND / OR。"
            )
            self.query_combo.setFocus()
            return

        try:
            boundary_re = core.compile_boundary(self._boundary_pattern)
        except ValueError as exc:
            QMessageBox.critical(self, "分隔符无效", str(exc))
            return

        self._remember_query(query)
        self._clear_result_state()
        self.search_query = query
        self._show_empty(
            "正在检索",
            "正在读取并拆分小说，命中的句子会显示在这里。",
            "TXT",
            None,
            "search",
        )
        self._set_searching(True)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()
        self._progress_hide_timer.stop()
        self._search_started = time.monotonic()
        self._elapsed_timer.start()
        self._status("正在读取文件…")
        self._footer("● 正在检索")
        self._log("开始检索：%s" % query)
        self._log("文件：%s" % self.source_path)
        self._log("分隔符：%s" % self._boundary_pattern)
        if core.has_lowercase_boolean_operator(query):
            self._log("提示：检测到小写 and / or，已按普通关键词处理。")

        worker = SearchWorker(
            self.source_path, query, self._boundary_pattern, parent=self
        )
        worker.phase.connect(self._on_search_phase)
        worker.progress.connect(self._on_search_progress)
        worker.succeeded.connect(self._on_search_succeeded)
        worker.failed.connect(self._on_search_failed)
        worker.canceled.connect(self._on_search_canceled)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def cancel_search(self):
        if self._worker is None or not self._worker.isRunning():
            return
        self._worker.cancel()
        self.search_btn.setEnabled(False)
        self.search_btn.setText("正在取消…")
        self._status("正在取消检索…", "warning")
        self._log("用户请求取消检索。")

    def _on_search_phase(self, text):
        self._status(text)
        self._log(text)
        if text == "正在比对广告句…":
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)

    def _on_search_progress(self, done, total):
        if total <= 0:
            return
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)
        self._status("正在检索… %s / %s 句" % (format(done, ","), format(total, ",")))

    def _tick_elapsed(self):
        if self._worker is None:
            return
        elapsed = time.monotonic() - self._search_started
        self.elapsed_label.setText("已用 %.1f 秒" % elapsed)

    def _on_search_succeeded(self, result):
        self.loaded = result.loaded
        self.source_path = result.path
        self.source_stat = result.source_stat
        self._update_metadata(result.loaded, result.char_count, len(result.sentences))
        self.result_path = result.result_path
        timings = result.timings
        timing_text = "读取 %.2fs · 拆分 %.2fs · 匹配 %.2fs" % (
            timings.get("read", 0.0),
            timings.get("split", 0.0),
            timings.get("match", 0.0),
        )
        if "write" in timings:
            timing_text += " · 写结果 %.2fs" % timings["write"]

        if not result.matched:
            self.matched = None
            self.sentences = None
            self.index_map = None
            self.result_path = None
            self._deletion_cache_valid = False
            self.count_badge.setText("0 条命中")
            self.delete_btn.setEnabled(False)
            self.open_result_btn.setEnabled(False)
            self.result_hint.setText("换个更短的关键词试试。")
            self.result_hint.setToolTip("")
            self._show_empty(
                "没有找到匹配句",
                "换更短、更稳定的关键词试试。",
                "0",
                "调整检索词",
                "query",
            )
            self.preview_stack.setCurrentIndex(0)
            self.tabs.setCurrentIndex(0)
            self._status("检索完成，未找到匹配句。", "warning")
            self._footer("● 未找到匹配句")
            self._log("检索完成，未找到匹配句。用时 %.2f 秒。" % timings.get("total", 0.0))
            self._log(timing_text)
            self._finish_elapsed(timings.get("total", 0.0))
            self._progress_hide_timer.start(1200)
            self._toast.show_message("没有找到匹配句，试试更短的关键词。", "info")
            return

        self.sentences = result.sentences
        self.matched = result.matched
        self.index_map = {
            sequence: index for sequence, index in enumerate(result.matched, 1)
        }
        self._deletion_cache_valid = True
        self.count_badge.setText("%s 条命中" % format(len(result.matched), ","))
        self.delete_btn.setEnabled(True)
        self.open_result_btn.setEnabled(True)
        self.result_hint.setText(
            "结果文件：%s" % os.path.basename(result.result_path)
        )
        self.result_hint.setToolTip(result.result_path)
        self._set_label_tone(self.output_preview, "")
        self._render_preview()
        self.preview_stack.setCurrentIndex(1)
        self.tabs.setCurrentIndex(0)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self._status(
            "检索完成：%s 条命中，用时 %.2f 秒。"
            % (format(len(result.matched), ","), timings.get("total", 0.0)),
            "success",
        )
        self._footer("● 检索完成，等待复核")
        self._log(
            "检索完成，共找到 %s 条广告句。" % format(len(result.matched), ",")
        )
        self._log(timing_text)
        self._log("检索结果已保存至：%s" % result.result_path)
        self._log("复核完成后点击“删除广告并保存”。")
        self._finish_elapsed(timings.get("total", 0.0))
        self._progress_hide_timer.start(3000)
        self._toast.show_message(
            "已找到 %s 条广告句，结果文件已生成。"
            % format(len(result.matched), ","),
            "success",
        )

    def _on_search_failed(self, message):
        self._log("检索失败：%s" % message)
        self._status("检索失败", "error")
        self._footer("● 检索失败")
        self.progress_bar.hide()
        self._show_empty(
            "检索失败",
            "检查文件编码或分隔符后重试。",
            "!",
            "重新检索",
            "search",
        )
        self.preview_stack.setCurrentIndex(0)
        self._finish_elapsed(0.0)
        QMessageBox.critical(self, "检索失败", message)

    def _on_search_canceled(self):
        self._log("检索已取消。")
        self._status("已取消检索。", "warning")
        self._footer("● 已取消检索")
        self.progress_bar.hide()
        self._show_empty(
            "已取消检索",
            "检索未完成，未生成结果文件。",
            "TXT",
            "重新检索",
            "search",
        )
        self.preview_stack.setCurrentIndex(0)
        self._finish_elapsed(0.0)

    def _finish_elapsed(self, total_seconds):
        if total_seconds:
            self.elapsed_label.setText("用时 %.2f 秒" % total_seconds)
        else:
            self.elapsed_label.setText("")

    def _on_worker_finished(self):
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        self._elapsed_timer.stop()
        self._set_searching(False)
        if self.progress_bar.value() == 0 and self.progress_bar.maximum() == 100:
            self.progress_bar.hide()

    def _set_searching(self, searching):
        self.search_btn.setText("取消检索" if searching else "检索")
        self.search_btn.setProperty("mode", "cancel" if searching else "")
        self.search_btn.setEnabled(True)
        style = self.search_btn.style()
        style.unpolish(self.search_btn)
        style.polish(self.search_btn)
        self.search_btn.update()

        for widget in (
            self.browse_btn,
            self.drop_zone,
            self.query_combo,
            self.output_btn,
            self.encoding_combo,
            self.preset_btn,
            self.boundary_btn,
        ):
            widget.setEnabled(not searching)
        if searching:
            self.delete_btn.setEnabled(False)
        else:
            self.delete_btn.setEnabled(self._deletion_cache_valid)
        self.open_output_btn.setEnabled(
            bool(self._last_output_dir or self.output_edit.text().strip())
        )
        if not searching:
            self.open_result_btn.setEnabled(
                bool(self.result_path and os.path.isfile(self.result_path))
            )

    def _update_metadata(self, loaded, char_count, sentence_count):
        encoding = ENCODING_LABELS.get(loaded.encoding, loaded.encoding)
        text = (
            "大小 %s  ·  编码 %s  ·  %s 字符  ·  %s 句"
            % (
                core.format_size(loaded.size),
                encoding,
                format(char_count, ","),
                format(sentence_count, ","),
            )
        )
        self.meta_label.setText(text)
        self.meta_label.setToolTip(text)

    # ---------------------------------------------------------------- 预览
    def _render_preview(self):
        if not self.matched or not self.sentences:
            self.preview.clear()
            return
        colors = self._colors
        total = len(self.matched)
        shown = self.matched[:200]
        terms = core.query_terms(self.search_query)
        item_style = "margin-bottom:8px;"
        head_style = (
            "color:%s; font-size:%dpx; margin-bottom:3px;"
            % (colors["muted"], max(11, self._font_size - 3))
        )
        seq_style = "color:%s; font-weight:bold;" % colors["primary"]
        body_style = "color:%s;" % colors["text"]
        items = []
        for sequence, index in enumerate(shown, 1):
            sentence = self.sentences[index]
            body = self._highlight_html(sentence, terms)
            items.append(
                '<table width="100%%" cellspacing="0" cellpadding="0"'
                ' bgcolor="%s" border="1" bordercolor="%s" style="%s">'
                '<tr><td style="padding:9px 11px;">'
                '<div style="%s">命中 <span style="%s">%d</span>'
                ' · 原文第 %s 句</div><div style="%s">%s</div>'
                "</td></tr></table>"
                % (
                    colors["surface"],
                    colors["border"],
                    item_style,
                    head_style,
                    seq_style,
                    sequence,
                    format(index + 1, ","),
                    body_style,
                    body,
                )
            )
        more = ""
        if total > len(shown):
            more = (
                '<div style="color:%s; padding:10px 2px 14px 2px; text-align:center;">'
                "仅预览前 %d 条，共 %s 条。完整内容见检索结果文件。</div>"
                % (colors["muted"], len(shown), format(total, ","))
            )
        header = (
            '<div style="color:%s; padding:0 2px 8px 2px;">'
            "共 %s 条命中，显示前 %d 条。</div>"
            % (colors["muted"], format(total, ","), len(shown))
        )
        body_open = (
            '<html><body style="background-color:transparent; color:%s;'
            ' font-family:\'Microsoft YaHei UI\'; font-size:%dpx; margin:0;">'
            % (colors["text"], self._font_size)
        )
        self.preview.setHtml(
            body_open + header + "".join(items) + more + "</body></html>"
        )

    def _highlight_html(self, sentence, terms):
        text = (sentence or "").strip() or "（空片段）"
        if len(text) > 600:
            text = text[:600] + "…"
        useful_terms = [term for term in terms if term]
        if not useful_terms:
            return html.escape(text).replace("\n", "<br>")
        pattern = re.compile(
            "|".join(re.escape(term) for term in sorted(useful_terms, key=len, reverse=True))
        )
        span_style = "background-color:%s; color:%s; font-weight:bold;" % (
            self._colors["highlight_bg"],
            self._colors["highlight_text"],
        )
        parts = []
        last = 0
        for match in pattern.finditer(text):
            parts.append(html.escape(text[last : match.start()]))
            parts.append(
                '<span style="%s">%s</span>'
                % (span_style, html.escape(match.group(0)))
            )
            last = match.end()
        parts.append(html.escape(text[last:]))
        return "".join(parts).replace("\n", "<br>")

    def _show_empty(self, title, subtitle, icon_text, action_text, action_mode):
        self.empty_icon.setText(icon_text)
        self.empty_title.setText(title)
        self.empty_sub.setText(subtitle)
        self._empty_action_mode = action_mode
        if action_text:
            self.empty_action.setText(action_text)
            self.empty_action.show()
        else:
            self.empty_action.hide()
        self.preview_stack.setCurrentIndex(0)

    def _on_empty_action(self):
        if self._empty_action_mode == "query":
            self._focus_query()
        elif self._empty_action_mode == "search":
            self.start_search()
        else:
            self.choose_file()

    # ---------------------------------------------------------------- 删除
    def delete_ads(self):
        if self._worker is not None and self._worker.isRunning():
            return
        if self.sentences is None or self.index_map is None:
            QMessageBox.warning(self, "请先检索", "请先执行检索，确认结果后再删除。")
            return
        if not self._deletion_cache_valid:
            QMessageBox.warning(
                self, "请重新检索", "本次删除缓存已失效，请重新检索后再删除。"
            )
            return
        if not self.source_path or not os.path.isfile(self.source_path):
            QMessageBox.critical(
                self, "源文件不存在", "找不到源文件，请重新选择并检索。"
            )
            self._clear_deletion_cache()
            return
        try:
            current_stat = os.stat(self.source_path)
        except OSError as exc:
            QMessageBox.critical(self, "读取失败", "无法读取源文件信息：\n%s" % exc)
            return
        if self.source_stat and (
            current_stat.st_size,
            current_stat.st_mtime_ns,
        ) != self.source_stat:
            QMessageBox.warning(
                self,
                "源文件已变化",
                "检索之后源文件被修改过。为避免删除错位，请重新检索。",
            )
            self._clear_deletion_cache()
            self._status("源文件已变化，请重新检索。", "warning")
            return

        output_dir = self.output_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "缺少输出目录", "请先选择输出目录。")
            return
        if not os.path.isdir(output_dir):
            QMessageBox.critical(
                self, "输出目录不存在", "输出目录不存在：\n%s" % output_dir
            )
            return
        if not self.result_path or not os.path.isfile(self.result_path):
            QMessageBox.critical(
                self,
                "结果文件不存在",
                "本次检索生成的结果文件已不存在，请重新检索。",
            )
            self._clear_deletion_cache()
            return
        try:
            lines = core.read_result_lines(self.result_path)
        except Exception as exc:
            QMessageBox.critical(
                self, "读取结果失败", "无法读取检索结果文件：\n%s" % exc
            )
            return

        seqs = core.parse_result_seq_lines(lines)
        known = seqs & set(self.index_map.keys())
        if not known:
            QMessageBox.information(
                self,
                "没有可删除项",
                "检索结果文件中没有保留任何有效序号。\n"
                "如果你删掉了全部条目，表示本次不删除任何广告。",
            )
            self._log("结果文件中没有保留有效序号，未执行删除。")
            return
        if len(known) != len(seqs):
            self._log(
                "忽略了 %d 个不属于本次检索的序号。" % (len(seqs) - len(known))
            )

        delete_indices = {self.index_map[sequence] for sequence in known}
        out_path = core.make_output_path(self.source_path, output_dir)
        if core.is_same_file(out_path, self.source_path):
            QMessageBox.critical(
                self,
                "输出路径冲突",
                "输出文件与源文件相同，拒绝覆盖。请更改输出目录或文件名。",
            )
            return

        total_matched = len(self.matched or [])
        percent = (len(known) / total_matched * 100.0) if total_matched else 0.0
        answer = QMessageBox.question(
            self,
            "确认删除",
            "将从副本中删除 %d 句广告（占命中 %d 句的 %.1f%%）。\n\n"
            "输出文件：\n%s\n\n原文件不会被修改。是否继续？"
            % (len(known), total_matched, percent, out_path),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            self._log("已取消删除。")
            return
        if os.path.exists(out_path):
            answer = QMessageBox.question(
                self,
                "目标文件已存在",
                "目标文件已存在：\n%s\n\n是否覆盖？" % out_path,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                self._log("已取消，未覆盖已有文件。")
                return

        encoding = self.encoding_combo.currentData()
        if encoding == "source":
            encoding = self.loaded.encoding if self.loaded else "utf-8-sig"
            self._log("输出编码跟随原文件：%s" % encoding)
        newline = self.loaded.newline if self.loaded else "\n"

        self._status("正在保存清理副本…")
        self._footer("● 正在保存")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            cleaned = core.join_sentences(self.sentences, delete_indices)
            core.write_text(out_path, cleaned, encoding=encoding, newline=newline)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            self._log("保存失败：%s" % exc)
            self._status("保存失败", "error")
            self._footer("● 保存失败")
            QMessageBox.critical(self, "保存失败", "无法写入输出文件：\n%s" % exc)
            return
        QApplication.restoreOverrideCursor()

        self._last_output = out_path
        self._last_output_dir = os.path.dirname(out_path)
        self.open_output_btn.setEnabled(True)
        self.output_preview.setText("已保存：%s" % os.path.basename(out_path))
        self.output_preview.setToolTip(out_path)
        self._set_label_tone(self.output_preview, "success")
        self._clear_deletion_cache()
        self.count_badge.setText("已保存")
        self.result_hint.setText("已保存：%s" % os.path.basename(out_path))
        self.result_hint.setToolTip(out_path)
        self._status("清理完成：%s 句广告已从副本中删除。" % format(len(known), ","), "success")
        self._footer("● 已保存清理副本")
        self._log("删除完成，共删除 %d 句。" % len(known))
        self._log("输出文件：%s" % out_path)
        self._log("已清空删除缓存；原文件未被修改。")
        self._toast.show_message(
            "已保存清理副本：%s" % os.path.basename(out_path), "success", 5200
        )

    def _clear_deletion_cache(self):
        self._deletion_cache_valid = False
        self.index_map = None
        self.source_stat = None
        self.delete_btn.setEnabled(False)

    def _clear_result_state(self):
        self._deletion_cache_valid = False
        self.sentences = None
        self.index_map = None
        self.matched = None
        self.result_path = None
        self.source_stat = None
        self.count_badge.setText("0 条命中")
        self.delete_btn.setEnabled(False)
        self.open_result_btn.setEnabled(False)
        self.preview.clear()
        self.preview_stack.setCurrentIndex(0)
        self.result_hint.setText("检索完成后生成 检索结果.txt")
        self.result_hint.setToolTip("")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        self._progress_hide_timer.stop()
        self.elapsed_label.setText("")
        self._show_empty(
            "还没有检索结果",
            "选择小说并输入检索词，结果会显示在这里。",
            "TXT",
            "选择小说",
            "file",
        )

    # ---------------------------------------------------------------- 其他
    def _rebuild_preset_menu(self):
        menu = self.preset_menu
        menu.clear()
        if self._presets:
            for label, query in self._presets:
                action = menu.addAction(label)
                action.setToolTip(query)
                action.triggered.connect(
                    lambda checked=False, q=query, name=label: self._apply_preset(name, q)
                )
        else:
            empty = menu.addAction("暂无常用规则")
            empty.setEnabled(False)
        menu.addSeparator()
        edit_action = menu.addAction("编辑常用规则…")
        edit_action.triggered.connect(self.show_settings)

    def show_settings(self):
        dialog = SettingsDialog(
            self, self._presets, self._font_size, self._colors
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        self._presets = dialog.result_presets()
        self._font_size = dialog.result_font_size()
        self._rebuild_preset_menu()
        self._apply_theme(self.current_theme, persist=False)
        self._save_settings()
        self._toast.show_message("设置已保存。", "success")

    def edit_boundary(self):
        if self._worker is not None and self._worker.isRunning():
            return
        dialog = BoundaryDialog(
            self,
            self._boundary_pattern,
            core.DEFAULT_BOUNDARY_PATTERN,
            self._colors,
            self._font_size,
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        pattern = dialog.get_pattern()
        if not pattern or pattern == self._boundary_pattern:
            return
        self._boundary_pattern = pattern
        self.boundary_re = core.compile_boundary(pattern)
        self._settings.setValue("boundary_pattern", pattern)
        self._settings.sync()
        self._update_boundary_hint()
        self._clear_result_state()
        self._show_empty(
            "分隔符已更新",
            "请重新检索以应用新分隔符。",
            "TXT",
            "重新检索",
            "search",
        )
        self._status("分隔符已更新，请重新检索。", "warning")
        self._log("分隔符已更新：%s" % pattern)

    def _update_boundary_hint(self):
        if self._boundary_pattern == core.DEFAULT_BOUNDARY_PATTERN:
            self.boundary_btn.setToolTip("当前：默认分隔符（句读 / 换行 / HTML 标签 / 右括号）\n点击编辑（Ctrl+E）")
        else:
            self.boundary_btn.setToolTip(
                "当前：自定义分隔符\n%s\n点击编辑（Ctrl+E）" % self._boundary_pattern
            )

    def show_help(self):
        dialog = HelpDialog(self, self._colors, self._font_size)
        dialog.exec_()

    def open_result_file(self):
        if self.result_path and os.path.isfile(self.result_path):
            self._open_path(self.result_path)
        else:
            QMessageBox.warning(
                self, "文件不存在", "检索结果文件不存在，请重新检索。"
            )

    def open_output_dir(self):
        directory = self._last_output_dir or self.output_edit.text().strip()
        if directory and os.path.isdir(directory):
            self._open_path(directory)
        else:
            QMessageBox.warning(self, "目录不存在", "输出目录不存在或尚未设置。")

    def _open_path(self, path):
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            QMessageBox.warning(self, "打开失败", "系统无法打开：\n%s" % path)

    def _log(self, message):
        stamp = time.strftime("%H:%M:%S")
        self.log_edit.appendPlainText("[%s] %s" % (stamp, message))
        scrollbar = self.log_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _clear_log(self):
        self.log_edit.clear()

    def _status(self, text, tone="normal"):
        self.status_label.setText(text)
        self.status_label.setProperty("tone", tone if tone != "normal" else "")
        style = self.status_label.style()
        style.unpolish(self.status_label)
        style.polish(self.status_label)
        self.status_label.update()

    def _footer(self, text):
        self.footer_status.setText(text)

    def _set_drop_active(self, active):
        self.drop_zone.setProperty("dragActive", "true" if active else "false")
        style = self.drop_zone.style()
        style.unpolish(self.drop_zone)
        style.polish(self.drop_zone)
        self.drop_zone.update()

    # ------------------------------------------------------------- 拖放/关闭
    def dragEnterEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            event.ignore()
            return
        urls = event.mimeData().urls()
        if any(
            url.isLocalFile() and core.is_txt_file(url.toLocalFile()) for url in urls
        ):
            event.acceptProposedAction()
            self._set_drop_active(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_drop_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._set_drop_active(False)
        for url in event.mimeData().urls():
            if url.isLocalFile() and core.is_txt_file(url.toLocalFile()):
                self.select_file(url.toLocalFile())
                event.acceptProposedAction()
                return
        event.ignore()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_toast") and self._toast.isVisible():
            self._toast._reposition()

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            answer = QMessageBox.question(
                self,
                "检索仍在进行",
                "检索还没有完成。确定取消并退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self._worker.cancel()
            if not self._worker.wait(8000):
                QMessageBox.warning(
                    self, "请稍候", "检索线程仍在停止，请稍后再关闭窗口。"
                )
                event.ignore()
                return
            self._worker = None
        self._save_settings()
        event.accept()


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    QCoreApplication.setOrganizationName("Dayrk0")
    QCoreApplication.setApplicationName("TXTAdCleaner")
    app.setStyle("Fusion")

    font = QFont("Microsoft YaHei UI", 10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)
    app.setWindowIcon(build_app_icon())
    _windows_app_id()

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
