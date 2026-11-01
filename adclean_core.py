# -*- coding: utf-8 -*-
"""小说广告清理工具的纯文本处理核心。

模块不依赖 PyQt5，便于单元测试与复用。所有函数只处理文本和文件，
不包含任何界面逻辑。
"""

from __future__ import annotations

import codecs
import os
import re
import tempfile
from dataclasses import dataclass

# 默认句子分隔符：句读、换行、HTML 闭合标签与常见右半边符号。
# 修改后由 compile_boundary() 统一外包一层捕获组，供 re.split() 使用。
DEFAULT_BOUNDARY_PATTERN = (
    r'[。！？!?\n]|</a>|</strong>|</span>|</div>|'
    r'\]|\)|\）|\】|\》|\"|\”|\'|\’|\}|\｝'
)

SENTENCE_BOUNDARY = re.compile("(" + DEFAULT_BOUNDARY_PATTERN + ")", re.IGNORECASE)

# 读取文件时依次尝试的编码；BOM 会先被单独识别。
TEXT_ENCODINGS = ("utf-8", "gbk", "gb18030", "big5")
UTF16_ENCODINGS = ("utf-16-le", "utf-16-be")

RESULT_FILE_NAME = "检索结果.txt"
RESULT_ENCODING = "utf-8-sig"

# 仅用于测试或把结果文件放到非桌面位置的高级覆盖项。
RESULT_DIR_ENV = "TXT_AD_CLEAN_RESULT_DIR"

RESULT_SEQ_RE = re.compile(r"^\s*[\[【]\s*(\d+)\s*[\]】]")


class TextDecodeError(ValueError):
    """文件无法用内置支持的编码解码。"""


@dataclass(frozen=True)
class LoadedText:
    """一次读取的完整结果。text 中的换行已统一为 ``\\n``。"""

    text: str
    encoding: str
    newline: str
    size: int
    had_bom: bool = False


def compile_boundary(pattern):
    """校验并编译用户提供的句子分隔符正则。

    返回的正则恰好包含一个捕获组，保证 ``re.split`` 的输出可以
    两两配对还原为“句子 + 分隔符”。非法输入抛出 ``ValueError``。
    """
    pattern = (pattern or "").strip()
    if not pattern:
        raise ValueError("分隔符正则不能为空。")

    try:
        boundary_re = re.compile("(" + pattern + ")", re.IGNORECASE)
    except re.error as exc:
        raise ValueError("正则表达式非法：%s" % exc) from exc

    if boundary_re.groups != 1:
        raise ValueError(
            "分隔符正则中不能包含捕获组括号 ( )。\n如需分组请改用非捕获组 (?:...) 。"
        )
    if boundary_re.search("") is not None:
        raise ValueError("分隔符正则不能匹配空字符串。")
    return boundary_re


def split_sentences(text, boundary_re=SENTENCE_BOUNDARY):
    """按分隔符拆分文本，每个句子元素保留末尾的分隔符。

    ``boundary_re`` 必须恰好包含一个捕获组，使 ``re.split`` 返回
    ``[文本, 分隔符, 文本, 分隔符, ..., 末尾残留]``。连续分隔符会产生
    空文本片段，配对后仍能保持原文顺序，删除整句时不会误删前一句的分隔符。
    """
    if boundary_re.groups != 1:
        raise ValueError("分隔符正则必须恰好包含一个捕获组。")

    parts = boundary_re.split(text)
    sentences = []

    def push(chunk):
        if not chunk:
            return
        if sentences and not chunk.strip():
            sentences[-1] += chunk
        else:
            sentences.append(chunk)

    for i in range(0, len(parts) - 1, 2):
        push(parts[i] + parts[i + 1])
    if parts:
        push(parts[-1])
    if text == "":
        return []
    return sentences


def parse_query_groups(query):
    """把检索表达式拆成“或组”的列表，每个或组是若干关键词的列表。

    仍然遵循原工具语义：``OR`` 分隔或组，``AND`` 连接同组关键词。
    额外容忍关键词两侧多余的空白和全角空格；``AND`` / ``OR`` 仍须大写，
    避免把英文短语里的 ``and`` / ``or`` 误当成操作符。
    """
    normalized = (query or "").replace("\u3000", " ").strip()
    if not normalized:
        return []

    groups = []
    for or_part in re.split(r"\s+OR\s+", normalized):
        or_part = or_part.strip()
        if not or_part:
            continue
        words = [word.strip() for word in re.split(r"\s+AND\s+", or_part)]
        words = [word for word in words if word]
        if words:
            groups.append(words)
    return groups


def parse_query(query):
    """返回匹配函数：句子满足任意一个或组的全部关键词即为命中。"""
    groups = parse_query_groups(query)

    def match(sentence):
        return any(all(word in sentence for word in group) for group in groups)

    return match


def query_terms(query):
    """按出现顺序返回去重后的全部关键词，供预览高亮使用。"""
    terms = []
    for group in parse_query_groups(query):
        for word in group:
            if word not in terms:
                terms.append(word)
    return terms


def has_lowercase_boolean_operator(query):
    """检测未大写的 and/or，用于给出界面提示（不改变匹配语义）。"""
    if not query:
        return False
    if re.search(r"\s(?:AND|OR)\s", query):
        return False
    return re.search(r"\s(?:and|or)\s", query) is not None


def detect_newline(text):
    """返回原文最主要的换行风格：``\\r\\n``、``\\r`` 或 ``\\n``。"""
    crlf = text.count("\r\n")
    rest = text.replace("\r\n", "")
    cr = rest.count("\r")
    lf = rest.count("\n")
    if crlf and crlf >= cr and crlf >= lf:
        return "\r\n"
    if cr > lf:
        return "\r"
    return "\n"


def normalize_newlines(text):
    """把 CRLF / CR 统一为 LF，便于检索和重建。"""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def decode_text(data):
    """按 BOM、UTF-8、GBK、GB18030、Big5 的顺序解码字节串。

    返回 ``(text, encoding, had_bom)``。UTF-16 仅在有 BOM 或存在明显
    的 NUL 字节分布时尝试，避免把普通单字节文本误解码成乱码。
    """
    if not data:
        return "", "utf-8", False

    if data.startswith(codecs.BOM_UTF8):
        return data.decode("utf-8-sig"), "utf-8-sig", True
    if data.startswith(codecs.BOM_UTF16_LE) or data.startswith(codecs.BOM_UTF16_BE):
        return data.decode("utf-16"), "utf-16", True

    if len(data) >= 4 and data.count(b"\x00") / len(data) > 0.1:
        for encoding in UTF16_ENCODINGS:
            try:
                text = data.decode(encoding)
            except UnicodeDecodeError:
                continue
            if text and "\x00" not in text:
                return text, encoding, False

    attempted = []
    for encoding in TEXT_ENCODINGS:
        try:
            return data.decode(encoding), encoding, False
        except UnicodeDecodeError:
            attempted.append(encoding)

    raise TextDecodeError(
        "无法识别文件编码（已尝试 %s）。请先将文件另存为 UTF-8 后重试。"
        % " / ".join(attempted)
    )


def read_text(path):
    """读取文本文件，自动识别编码与换行风格。

    ``LoadedText.text`` 已统一为 LF；写回时用 ``LoadedText.newline``
    恢复原换行风格，避免清理后整本书的换行被改写。
    """
    with open(path, "rb") as f:
        data = f.read()

    text, encoding, had_bom = decode_text(data)
    newline = detect_newline(text)
    return LoadedText(
        text=normalize_newlines(text),
        encoding=encoding,
        newline=newline,
        size=len(data),
        had_bom=had_bom,
    )


def write_text(path, content, encoding=RESULT_ENCODING, newline="\n"):
    """原子写入文本；失败时不会留下半截文件。

    ``content`` 中的换行应统一为 LF，函数会按 ``newline`` 还原。
    """
    content = normalize_newlines(content)
    directory = os.path.dirname(os.path.abspath(path)) or os.curdir
    fd, temp_path = tempfile.mkstemp(prefix=".adclean-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline=newline) as f:
            f.write(content)
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def get_desktop_dir():
    """返回结果文件目录；支持测试覆盖与 OneDrive 桌面重定向。"""
    override = os.environ.get(RESULT_DIR_ENV)
    if override:
        return override

    home = os.path.expanduser("~")
    candidates = [os.path.join(home, "Desktop")]
    onedrive = os.environ.get("OneDrive")
    if onedrive:
        candidates.append(os.path.join(onedrive, "Desktop"))
        candidates.append(os.path.join(onedrive, "桌面"))
    candidates.append(os.path.join(home, "OneDrive", "Desktop"))
    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            return candidate
    return home


def parse_result_seq_lines(lines):
    """从检索结果文本行中提取保留的序号。

    兼容 ``[12]`` 与 ``【12】``；空行、总结行和无法解析的行会被忽略。
    """
    seqs = set()
    for line in lines:
        match = RESULT_SEQ_RE.match(line)
        if match:
            seqs.add(int(match.group(1)))
    return seqs


def write_result_file(path, sentences):
    """把命中句写成桌面检索结果格式：``[序号] 句子`` + 总计行。"""
    lines = []
    for seq, sentence in enumerate(sentences, 1):
        display = sentence.replace("\n", " ").strip()
        lines.append("[%d] %s" % (seq, display))
    lines.append("共找到 %d 条广告句" % len(sentences))
    write_text(path, "\n".join(lines), encoding=RESULT_ENCODING, newline=os.linesep)


def read_result_lines(path):
    """读取用户可能用记事本另存过编码的检索结果文件。"""
    return read_text(path).text.splitlines()


def join_sentences(sentences, delete_indices):
    """丢弃指定下标的句子元素，其余按原顺序拼接。"""
    return "".join(
        sentence for index, sentence in enumerate(sentences) if index not in delete_indices
    )


def make_output_path(source_path, output_dir):
    """生成 ``原文件名去广告.txt``。

    若源文件名已含“去广告”，追加 ``_clean``，避免输出路径与源文件相同。
    """
    base, ext = os.path.splitext(os.path.basename(source_path))
    if not ext:
        ext = ".txt"
    if base.endswith("去广告"):
        name = base + "_clean" + ext
    else:
        name = base + "去广告" + ext
    return os.path.join(output_dir, name)


def is_same_file(path_a, path_b):
    """判断两个路径是否指向同一个文件（不要求文件已存在）。"""
    try:
        return os.path.samefile(path_a, path_b)
    except OSError:
        return os.path.normcase(os.path.abspath(path_a)) == os.path.normcase(
            os.path.abspath(path_b)
        )


def is_txt_file(path):
    return os.path.splitext(path)[1].lower() == ".txt"


def format_size(num_bytes):
    """把字节数格式化为便于阅读的字符串。"""
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return "%d B" % int(value)
            return "%.1f %s" % (value, unit)
        value /= 1024
    return "%d B" % num_bytes
