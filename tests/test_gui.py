# -*- coding: utf-8 -*-
"""离屏 GUI 集成测试：检索、结果文件、删除与安全校验。"""

import importlib.util
import os
import shutil
import sys
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts=false")

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

TEST_TMP_ROOT = Path(__file__).resolve().parent / "_tmp"
TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)

SAMPLE_TEXT = (
    "第一章 开端\r\n"
    "这是正文第一句。\r\n"
    "请访问 www.example.com 获取更多内容。\r\n"
    "关注公众号：书友之家，每天更新。\r\n"
    "这是正文第二句！\r\n"
)


def make_temp_dir(prefix):
    path = TEST_TMP_ROOT / (prefix + uuid.uuid4().hex[:12])
    path.mkdir()
    return path


def load_gui_module():
    spec = importlib.util.spec_from_file_location(
        "novel_cleaner_gui", PROJECT_ROOT / "小说广告清理工具.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setFont(QFont("Microsoft YaHei UI", 10))
        cls.gui = load_gui_module()

    def setUp(self):
        self.case_dir = make_temp_dir("gui-")
        self.settings_dir = self.case_dir / "settings"
        self.settings_dir.mkdir()
        self.result_dir = self.case_dir / "results"
        self.result_dir.mkdir()
        os.environ["TXT_AD_CLEAN_SETTINGS_DIR"] = str(self.settings_dir)
        os.environ["TXT_AD_CLEAN_RESULT_DIR"] = str(self.result_dir)
        self.windows = []
        self._critical_patcher = mock.patch.object(
            self.gui.QMessageBox,
            "critical",
            new=staticmethod(lambda *args, **kwargs: self.gui.QMessageBox.Ok),
        )
        self._critical_patcher.start()

    def tearDown(self):
        for window in self.windows:
            window.close()
        self.app.processEvents()
        self._critical_patcher.stop()
        shutil.rmtree(self.case_dir, ignore_errors=True)

    def make_window(self):
        window = self.gui.MainWindow()
        window.resize(1180, 780)
        window.show()
        self.app.processEvents()
        self.windows.append(window)
        return window

    def make_sample(self, text=SAMPLE_TEXT, encoding="utf-8", name="样例小说.txt"):
        path = self.case_dir / name
        path.write_bytes(text.encode(encoding))
        return path

    def search(self, window, query):
        window.query_combo.setEditText(query)
        window.start_search()
        deadline = time.time() + 20
        while window._worker is not None and time.time() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        for _ in range(30):
            self.app.processEvents()
            time.sleep(0.002)
        self.assertIsNone(window._worker, "检索线程未在超时前结束")

    def delete_with_yes(self, window):
        with mock.patch.object(
            self.gui.QMessageBox,
            "question",
            new=staticmethod(lambda *args, **kwargs: self.gui.QMessageBox.Yes),
        ):
            window.delete_ads()
        self.app.processEvents()

    def test_search_and_delete_end_to_end(self):
        source = self.make_sample()
        before = source.read_bytes()
        window = self.make_window()
        window.select_file(str(source))

        self.assertEqual(Path(window.source_path), source.resolve())
        self.assertEqual(Path(window.output_edit.text()), source.parent.resolve())
        self.assertEqual(window.output_edit.cursorPosition(), 0)

        self.search(window, "www OR 公众号")
        self.assertEqual(len(window.sentences), 5)
        self.assertEqual(window.matched, [2, 3])
        self.assertTrue(window._deletion_cache_valid)
        self.assertTrue(window.delete_btn.isEnabled())
        self.assertEqual(window.count_badge.text(), "2 条命中")

        result_path = self.result_dir / "检索结果.txt"
        self.assertEqual(
            self.gui.core.read_text(result_path).text.splitlines(),
            [
                "[1] 请访问 www.example.com 获取更多内容。",
                "[2] 关注公众号：书友之家，每天更新。",
                "共找到 2 条广告句",
            ],
        )
        self.assertGreater(len(window.preview.toHtml()), 1000)

        self.delete_with_yes(window)
        output = source.with_name("样例小说去广告.txt")
        self.assertTrue(output.exists())
        self.assertEqual(
            output.read_bytes().decode("utf-8-sig"),
            "第一章 开端\r\n这是正文第一句。\r\n这是正文第二句！\r\n",
        )
        self.assertEqual(source.read_bytes(), before)
        self.assertFalse(window._deletion_cache_valid)
        self.assertFalse(window.delete_btn.isEnabled())
        self.assertEqual(window.count_badge.text(), "已保存")
        self.assertTrue(window.open_output_btn.isEnabled())

        old_theme = window.current_theme
        window._toggle_theme()
        self.app.processEvents()
        self.assertNotEqual(window.current_theme, old_theme)
        self.assertIn("命中", window.preview.toHtml())

    def test_no_match_still_refreshes_result_file(self):
        source = self.make_sample()
        window = self.make_window()
        window.select_file(str(source))
        self.search(window, "不存在的广告词")

        self.assertIsNone(window.matched)
        self.assertIsNone(window.sentences)
        self.assertFalse(window._deletion_cache_valid)
        self.assertFalse(window.delete_btn.isEnabled())
        self.assertIsNone(window.result_path)
        self.assertFalse(window.open_result_btn.isEnabled())
        result_path = self.result_dir / "检索结果.txt"
        self.assertTrue(result_path.exists())
        self.assertEqual(
            self.gui.core.read_text(result_path).text.splitlines(),
            ["共找到 0 条广告句"],
        )

    def test_source_change_blocks_delete(self):
        source = self.make_sample()
        window = self.make_window()
        window.select_file(str(source))
        self.search(window, "www OR 公众号")

        with mock.patch.object(
            self.gui.QMessageBox,
            "warning",
            new=mock.Mock(return_value=self.gui.QMessageBox.Ok),
        ) as warning, mock.patch.object(
            self.gui.QMessageBox,
            "question",
            new=staticmethod(lambda *args, **kwargs: self.gui.QMessageBox.Yes),
        ):
            source.write_bytes(source.read_bytes() + b"modified")
            window.delete_ads()

        self.assertTrue(warning.called)
        self.assertFalse(source.with_name("样例小说去广告.txt").exists())
        self.assertFalse(window._deletion_cache_valid)
        self.assertFalse(window.delete_btn.isEnabled())

    def test_edited_result_file_controls_deletion(self):
        source = self.make_sample()
        window = self.make_window()
        window.select_file(str(source))
        self.search(window, "www OR 公众号")

        result_path = self.result_dir / "检索结果.txt"
        only_first = "[1] " + window.sentences[2].replace("\n", " ").strip()
        self.gui.core.write_text(
            result_path,
            only_first + "\n共找到 1 条广告句",
            encoding="gbk",
        )
        self.delete_with_yes(window)

        output = source.with_name("样例小说去广告.txt")
        text = output.read_bytes().decode("utf-8-sig")
        self.assertNotIn("www.example.com", text)
        self.assertIn("关注公众号：书友之家，每天更新。", text)

    def test_gbk_source_and_follow_source_encoding(self):
        source = self.make_sample(encoding="gbk", name="GBK小说.txt")
        window = self.make_window()
        window.select_file(str(source))
        self.search(window, "www OR 公众号")
        window.encoding_combo.setCurrentIndex(2)
        self.delete_with_yes(window)

        output = source.with_name("GBK小说去广告.txt")
        data = output.read_bytes()
        text = data.decode("gbk")
        self.assertNotIn("www.example.com", text)
        self.assertNotIn("公众号", text)
        self.assertIn("这是正文第二句！", text)
        self.assertNotIn(b"\n\n", data)
        self.assertNotIn(b"\r\r", data)

    def test_boundary_dialog_validates_immediately(self):
        window = self.make_window()
        dialog = self.gui.BoundaryDialog(
            window,
            self.gui.core.DEFAULT_BOUNDARY_PATTERN,
            self.gui.core.DEFAULT_BOUNDARY_PATTERN,
            window._colors,
        )
        self.assertTrue(dialog.save_btn.isEnabled())
        self.assertIn("正则有效", dialog.status_label.text())
        self.assertGreater(len(dialog.preview.toHtml()), 100)

        dialog.pattern_edit.setPlainText("(")
        deadline = time.time() + 1.0
        while time.time() < deadline and dialog.save_btn.isEnabled():
            self.app.processEvents()
            time.sleep(0.02)
        self.assertFalse(dialog.save_btn.isEnabled())

        dialog.pattern_edit.setPlainText(self.gui.core.DEFAULT_BOUNDARY_PATTERN)
        deadline = time.time() + 1.0
        while time.time() < deadline and not dialog.save_btn.isEnabled():
            self.app.processEvents()
            time.sleep(0.02)
        self.assertTrue(dialog.save_btn.isEnabled())
        dialog.close()

    def test_help_dialog_constructs(self):
        window = self.make_window()
        dialog = self.gui.HelpDialog(window, window._colors)
        browser = dialog.findChild(self.gui.QTextBrowser)
        self.assertIsNotNone(browser)
        self.assertIn("使用说明", browser.toPlainText())
        dialog.close()

    def test_default_font_and_status_pill(self):
        window = self.make_window()
        self.assertEqual(window._font_size, 15)
        self.assertEqual(window.left_scroll.width(), 430)
        self.assertEqual(window.status_label.objectName(), "ResultStatus")
        self.assertEqual(window.status_label.text(), "就绪，等待选择小说")
        self.assertTrue(window._font_tokens()["fs_base"].endswith("px"))

    def test_settings_dialog_collects_presets_and_font(self):
        window = self.make_window()
        dialog = self.gui.SettingsDialog(
            window, list(window._presets), window._font_size, window._colors
        )
        self.assertEqual(dialog.table.rowCount(), 6)
        self.assertEqual(dialog.font_spin.value(), 15)

        dialog.font_spin.setValue(18)
        dialog._save()
        self.assertEqual(dialog.result_font_size(), 18)
        self.assertEqual(len(dialog.result_presets()), 6)

        dialog.close()


if __name__ == "__main__":
    unittest.main()
