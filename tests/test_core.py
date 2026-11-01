# -*- coding: utf-8 -*-
"""adclean_core 的单元测试。"""

import codecs
import os
import shutil
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import adclean_core as core

TEST_TMP_ROOT = Path(__file__).resolve().parent / "_tmp"
TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)


def make_temp_dir(prefix):
    path = TEST_TMP_ROOT / (prefix + uuid.uuid4().hex[:12])
    path.mkdir()
    return path


class BoundaryTests(unittest.TestCase):
    def test_default_pattern_compiles_with_one_group(self):
        self.assertEqual(core.SENTENCE_BOUNDARY.groups, 1)

    def test_compile_boundary_rejects_invalid_input(self):
        for pattern in ("", "(", r"[。]|(a)", r"[。]?"):
            with self.subTest(pattern=pattern):
                with self.assertRaises(ValueError):
                    core.compile_boundary(pattern)

    def test_custom_boundary(self):
        boundary = core.compile_boundary(r"[。\n]")
        self.assertEqual(
            core.split_sentences("A。B\nC", boundary),
            ["A。", "B\n", "C"],
        )

    def test_split_keeps_text_and_merges_blank_fragments(self):
        text = "第一句。\n第二句！尾"
        self.assertEqual(core.split_sentences(text), ["第一句。\n", "第二句！", "尾"])
        self.assertEqual("".join(core.split_sentences(text)), text)

        text = "A。\n\nB。\n"
        self.assertEqual(core.split_sentences(text), ["A。\n\n", "B。\n"])
        self.assertEqual("".join(core.split_sentences(text)), text)

    def test_split_empty_text(self):
        self.assertEqual(core.split_sentences(""), [])

    def test_split_requires_single_capture_group(self):
        import re

        with self.assertRaises(ValueError):
            core.split_sentences("A。", re.compile("。"))


class QueryTests(unittest.TestCase):
    def test_groups_support_full_width_space(self):
        self.assertEqual(
            core.parse_query_groups("A\u3000OR\u3000B AND C"),
            [["A"], ["B", "C"]],
        )

    def test_or_groups_and_and_terms(self):
        match = core.parse_query("A OR B AND C")
        self.assertTrue(match("A"))
        self.assertTrue(match("B C"))
        self.assertFalse(match("B"))
        self.assertFalse(match("C"))

    def test_empty_query_matches_nothing(self):
        self.assertFalse(core.parse_query("")("任意句子"))

    def test_operators_must_be_uppercase(self):
        self.assertEqual(core.parse_query_groups("foo and bar"), [["foo and bar"]])
        self.assertTrue(core.has_lowercase_boolean_operator("foo and bar"))
        self.assertFalse(core.has_lowercase_boolean_operator("foo AND bar"))

    def test_terms_are_deduplicated_in_order(self):
        self.assertEqual(core.query_terms("A OR B AND A"), ["A", "B"])

    def test_matching_is_case_sensitive(self):
        match = core.parse_query("广告")
        self.assertTrue(match("这里有广告"))
        self.assertFalse(match("这里有廣告"))


class NewlineTests(unittest.TestCase):
    def test_detect_newline(self):
        self.assertEqual(core.detect_newline("a\r\nb\r\n"), "\r\n")
        self.assertEqual(core.detect_newline("a\nb\n"), "\n")
        self.assertEqual(core.detect_newline("a\rb\r"), "\r")
        self.assertEqual(core.detect_newline("a\r\nb\nc"), "\r\n")

    def test_normalize_newlines(self):
        self.assertEqual(core.normalize_newlines("a\r\nb\rc\n"), "a\nb\nc\n")


class EncodingTests(unittest.TestCase):
    def test_decode_utf8_and_bom(self):
        self.assertEqual(core.decode_text("中文".encode("utf-8")), ("中文", "utf-8", False))
        self.assertEqual(
            core.decode_text("中文".encode("utf-8-sig")),
            ("中文", "utf-8-sig", True),
        )

    def test_decode_gbk_and_gb18030(self):
        self.assertEqual(core.decode_text("广告".encode("gbk")), ("广告", "gbk", False))
        self.assertEqual(
            core.decode_text("𠀀".encode("gb18030")),
            ("𠀀", "gb18030", False),
        )

    def test_decode_utf16_with_bom(self):
        text, encoding, had_bom = core.decode_text("中文广告".encode("utf-16"))
        self.assertEqual((text, encoding, had_bom), ("中文广告", "utf-16", True))
        data = codecs.BOM_UTF16_BE + "中文广告".encode("utf-16-be")
        text, encoding, had_bom = core.decode_text(data)
        self.assertEqual((text, encoding, had_bom), ("中文广告", "utf-16", True))

    def test_decode_empty_and_invalid(self):
        self.assertEqual(core.decode_text(b""), ("", "utf-8", False))
        with self.assertRaises(core.TextDecodeError):
            core.decode_text(b"\xff\xff")


class FileIoTests(unittest.TestCase):
    def setUp(self):
        self.root = make_temp_dir("core-")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_read_text_detects_gbk_and_crlf(self):
        path = self.root / "gbk.txt"
        path.write_bytes("第一行\r\n第二行\r\n".encode("gbk"))
        loaded = core.read_text(path)
        self.assertEqual(loaded.text, "第一行\n第二行\n")
        self.assertEqual(loaded.encoding, "gbk")
        self.assertEqual(loaded.newline, "\r\n")
        self.assertEqual(loaded.size, path.stat().st_size)

    def test_write_text_restores_newline_and_bom(self):
        path = self.root / "out.txt"
        core.write_text(path, "第一行\n第二行\n", encoding="utf-8-sig", newline="\r\n")
        self.assertTrue(path.read_bytes().startswith(codecs.BOM_UTF8))
        self.assertEqual(
            path.read_bytes()[3:],
            "第一行\r\n第二行\r\n".encode("utf-8"),
        )

    def test_write_text_cleans_temp_file(self):
        path = self.root / "out.txt"
        core.write_text(path, "内容", encoding="utf-8", newline="\n")
        self.assertEqual(list(self.root.glob(".adclean-*")), [])

    def test_result_file_format_has_no_blank_lines(self):
        path = self.root / "检索结果.txt"
        core.write_result_file(path, ["广告一\n", "广告二"])
        loaded = core.read_text(path)
        self.assertEqual(
            loaded.text.splitlines(),
            ["[1] 广告一", "[2] 广告二", "共找到 2 条广告句"],
        )
        self.assertNotIn("\n\n", loaded.text)

    def test_read_result_lines_tolerates_ansi_encoding(self):
        path = self.root / "检索结果.txt"
        core.write_text(path, "[1] 广告\n共找到 1 条广告句", encoding="gbk")
        self.assertEqual(
            core.read_result_lines(path),
            ["[1] 广告", "共找到 1 条广告句"],
        )


class ResultTests(unittest.TestCase):
    def test_parse_seq_lines(self):
        self.assertEqual(
            core.parse_result_seq_lines(
                ["[1] 广告", "【2】广告二", "共找到 2 条广告句", "[x] 不是序号"]
            ),
            {1, 2},
        )

    def test_join_sentences(self):
        sentences = ["A。", "\n", "B。"]
        self.assertEqual(core.join_sentences(sentences, {1}), "A。B。")

    def test_make_output_path(self):
        self.assertEqual(
            core.make_output_path(os.path.join("a", "小说.txt"), "out"),
            os.path.join("out", "小说去广告.txt"),
        )
        self.assertEqual(
            core.make_output_path(os.path.join("a", "小说去广告.txt"), "a"),
            os.path.join("a", "小说去广告_clean.txt"),
        )

    def test_same_file_and_txt_check(self):
        tmp = make_temp_dir("same-")
        try:
            path = tmp / "a.txt"
            path.write_text("x", encoding="utf-8")
            self.assertTrue(core.is_same_file(path, path))
            self.assertFalse(core.is_same_file(path, tmp / "b.txt"))
            self.assertTrue(core.is_txt_file("a.TXT"))
            self.assertFalse(core.is_txt_file("a.md"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class MiscTests(unittest.TestCase):
    def test_format_size(self):
        self.assertEqual(core.format_size(0), "0 B")
        self.assertEqual(core.format_size(1024), "1.0 KB")
        self.assertEqual(core.format_size(1536), "1.5 KB")
        self.assertEqual(core.format_size(1024 * 1024), "1.0 MB")

    def test_desktop_dir_env_override(self):
        tmp = make_temp_dir("desktop-")
        try:
            with mock.patch.dict(os.environ, {core.RESULT_DIR_ENV: str(tmp)}):
                self.assertEqual(core.get_desktop_dir(), str(tmp))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
