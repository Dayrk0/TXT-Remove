# -*- coding: utf-8 -*-
"""
小说广告清理工具（PyQt5 版）
============================
从 TXT 小说文件中查找并删除广告语句，带现代化 GUI 与可编辑检索结果。

运行环境：
    # 运行前请安装 PyQt5：pip install PyQt5
    # 或使用虚拟环境：python -m venv venv → venv\\Scripts\\activate → pip install PyQt5

与 Tkinter 版相比的三大改进：
    1. 现代化 PyQt5 界面（Fusion 风格，默认 800×400）
    2. 支持手动编辑“检索结果.txt”后按序号删除（删除依据是序号而非内容）
    3. 输出目录自定义，输出为“原文件名去广告.txt”，不修改原文件

本次优化（prompt4）：
    1. 扩展句子边界分隔符：增加右引号（” " ’ '）、右括号（） ）、右书名号（》）、
       右方括号（】）、右大括号（｝ }），保留原有句读、换行与 HTML 闭合标签。
    2. 界面布局更宽松：默认 850×500（最小 750×420），加大间距与边距，
       输入框固定高度，日志区 6 行，字体 Microsoft YaHei 9pt。
    3. 新增“编辑分隔符”按钮与模态对话框，分隔符正则可在运行时修改并即时生效。
    4. 输出目录下方新增提示文字，引导用户先编辑“检索结果.txt”再删除。
"""

import os
import re
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QVBoxLayout, QFileDialog, QMessageBox, QTextEdit,
    QDialog, QPlainTextEdit,
)

# 默认句子分隔符正则（字符串形式，不含 re.compile 包裹）。
# 内容：原有句读/换行 + HTML 闭合标签 + 各类右半边符号（引号、括号、书名号、大括号等）。
# 用户可通过“编辑分隔符”对话框修改，运行中以实例变量 self.boundary_pattern 为准。
# 注意：不能写成 (?<=...|</a>|...) 后行断言形式 —— Python 的 re 只支持固定宽度
# 后行断言，宽度不同的分支会报错 "look-behind requires fixed-width pattern"。
# 因此实际编译时统一外包一层捕获组，由 split_sentences() 把分隔符拼回前一个元素，
# 语义与"分隔符保留在句末"完全一致。
DEFAULT_BOUNDARY_PATTERN = (
    r'[。！？!?\n]|</a>|</strong>|</span>|</div>|'
    r'\]|\)|\）|\】|\》|\"|\”|\'|\’|\}|\｝'
)

# 模块级默认编译版本（带单个捕获组；实际检索使用 App 实例中的 self._boundary_re）
SENTENCE_BOUNDARY = re.compile("(" + DEFAULT_BOUNDARY_PATTERN + ")", re.IGNORECASE)

# 读取文件时依次尝试的编码顺序
ENCODINGS = ('utf-8-sig', 'gbk', 'gb18030')

# 桌面上的检索结果文件名
RESULT_FILE_NAME = "检索结果.txt"


def split_sentences(text, boundary_re=SENTENCE_BOUNDARY):
    """
    按 boundary_re 拆分文本，每个句子元素包含末尾的分隔符。

    boundary_re 必须恰好包含一个捕获组，使 re.split 返回
    [文本, 分隔符, 文本, 分隔符, ..., 末尾残留]。
    这里将每个"文本 + 分隔符"配对成一句，末尾残留单独成句，
    与原始写法 re.split(r'(?<=[。！？!?\n])', text) 的结果完全一致。
    """
    parts = boundary_re.split(text)
    sentences = []
    i = 0
    while i < len(parts) - 1:
        sentences.append(parts[i] + parts[i + 1])
        i += 2
    if parts:
        sentences.append(parts[-1])  # 末尾残留（无分隔符）
    return sentences


def parse_query(query):
    """
    解析检索表达式，返回匹配函数（输入句子 -> 是否匹配）。
    逻辑与原 Tkinter 版完全一致：
        - 以 ' OR ' 拆分为多个"与组"，组内以 ' AND ' 拆分为多个词；
        - 句子满足任意一个与组（组内所有词都出现）即匹配。
    """
    def build_group_matcher(group):
        # 过滤空白词，避免 "" in 句子 恒为真
        words = [w for w in group.split(' AND ') if w]
        return lambda sent: all(w in sent for w in words)

    or_groups = [g for g in query.split(' OR ') if g.strip()]
    group_matchers = [build_group_matcher(g) for g in or_groups]

    def match(sentence):
        return any(m(sentence) for m in group_matchers)

    return match


def read_text(path):
    """按 ENCODINGS 顺序尝试读取文件，返回 (文本, 实际使用的编码)。"""
    last_error = None
    for encoding in ENCODINGS:
        try:
            with open(path, 'r', encoding=encoding) as f:
                return f.read(), encoding
        except UnicodeDecodeError as e:
            last_error = e
    raise last_error


def write_text(path, content):
    """以 UTF-8（带 BOM）写入文本，确保 Windows 记事本正常显示中文。"""
    with open(path, 'w', encoding='utf-8-sig') as f:
        f.write(content)


def get_desktop_dir():
    """返回桌面目录；若不存在则回退到用户主目录。"""
    desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    return desktop if os.path.isdir(desktop) else os.path.expanduser('~')


def parse_result_seq_lines(lines):
    """
    从 检索结果.txt 的行中提取有效序号集合。
    跳过空行、以“共找到”开头的总结行、以及无法解析出 [数字] 的行。
    例：["[1] 广告A。", "共找到 2 条广告句", "", "用户手动添加的文字"] -> {1}
    """
    seqs = set()
    for line in lines:
        m = re.match(r'\s*\[(\d+)\]', line)
        if m:
            seqs.add(int(m.group(1)))
    return seqs


class BoundaryDialog(QDialog):
    """“编辑句子分隔符”模态对话框：预填当前正则，可恢复默认，保存前校验。"""

    def __init__(self, parent=None, current_pattern="", default_pattern=""):
        super().__init__(parent)
        self.setWindowTitle("编辑句子分隔符")
        self.setModal(True)
        self.setMinimumSize(560, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hint = QLabel(
            "修改句子分割用的正则表达式（只需分隔符内容，无需 re.compile 包裹）。\n"
            "保存时会校验正则是否合法，非法则不会关闭。"
        )
        layout.addWidget(hint)

        self.pattern_edit = QPlainTextEdit()
        self.pattern_edit.setPlainText(current_pattern)
        layout.addWidget(self.pattern_edit, 1)

        btn_row = QHBoxLayout()
        reset_btn = QPushButton("恢复默认")
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch(1)
        save_btn = QPushButton("保存并关闭")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        self._default_pattern = default_pattern
        self._saved_pattern = None

    def _reset(self):
        """将文本框内容重置为程序默认的分隔符正则。"""
        self.pattern_edit.setPlainText(self._default_pattern)

    def _save(self):
        """校验并保存：正则非法或捕获组数量不对时弹出警告，不关闭对话框。"""
        pattern = self.pattern_edit.toPlainText().strip()
        if not pattern:
            QMessageBox.warning(self, "正则错误", "分隔符正则不能为空。")
            return
        try:
            rx = re.compile("(" + pattern + ")", re.IGNORECASE)
        except re.error as e:
            QMessageBox.warning(self, "正则错误", "正则表达式非法，请检查：\n%s" % e)
            return
        # 程序会外包一层捕获组，若用户自带捕获组则总数为 2+，
        # 会让 re.split 返回元组、句子配对逻辑失效，必须阻止。
        # 用 rx.groups 直接数捕获组，不依赖探测串是否命中。
        if rx.groups != 1:
            QMessageBox.warning(
                self, "正则错误",
                "分隔符正则中不能包含捕获组括号 ( )。\n如需分组请改用非捕获组 (?:...) 。",
            )
            return
        self._saved_pattern = pattern
        self.accept()

    def get_pattern(self):
        """返回校验通过的分隔符正则字符串（未保存成功时为 None）。"""
        return self._saved_pattern


class AdCleanerApp(QWidget):
    """主窗口界面与业务逻辑（PyQt5）。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("小说广告清理工具")
        self.resize(850, 500)
        self.setMinimumSize(750, 420)

        # 检索缓存（供“删除广告”按钮使用）
        self.sentences = None   # 拆分后的句子元素列表
        self.index_map = None   # {序号: 句子在 sentences 中的索引}
        self.source_path = None # 源文件路径

        # 句子分隔符正则（可在“编辑分隔符”对话框中修改，检索/删除即时生效）
        self.boundary_pattern = DEFAULT_BOUNDARY_PATTERN
        self._boundary_re = SENTENCE_BOUNDARY

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)          # 控件之间间距
        main_layout.setContentsMargins(15, 15, 15, 15)  # 主布局外边距

        # 第 1 行：文件选择
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row1.addWidget(QLabel("文件："))
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        self.file_edit.setFixedHeight(28)
        row1.addWidget(self.file_edit, 1)
        self.browse_file_btn = QPushButton("浏览")
        self.browse_file_btn.clicked.connect(self.choose_file)
        row1.addWidget(self.browse_file_btn)

        # 第 2 行：检索词输入 + “编辑分隔符”按钮
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(QLabel("检索词："))
        self.query_edit = QLineEdit()
        self.query_edit.setFixedHeight(28)
        self.query_edit.setPlaceholderText("支持 AND / OR 组合，如：小说 AND 广告 OR 网址")
        row2.addWidget(self.query_edit, 1)
        self.search_btn = QPushButton("检索")
        self.search_btn.clicked.connect(self.do_search)
        row2.addWidget(self.search_btn)
        self.edit_btn = QPushButton("编辑分隔符")
        self.edit_btn.clicked.connect(self.edit_boundary)
        row2.addWidget(self.edit_btn)

        # 第 3 行：输出目录选择
        row3 = QHBoxLayout()
        row3.setSpacing(8)
        row3.addWidget(QLabel("输出目录："))
        self.output_edit = QLineEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setFixedHeight(28)
        self.output_edit.setPlaceholderText("请选择输出目录（清理后的文件保存于此）")
        row3.addWidget(self.output_edit, 1)
        self.browse_out_btn = QPushButton("浏览")
        self.browse_out_btn.clicked.connect(self.choose_output_dir)
        row3.addWidget(self.browse_out_btn)

        # 提示文字（优化四）：引导用户先编辑检索结果再删除
        hint = QLabel(
            "提示：检索后请先打开桌面上的“检索结果.txt”，手动删除您不想清理的条目并保存，"
            "再点击“删除广告”。序号被删的句子将不会被删除。"
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hint.setStyleSheet("color: #555555;")
        hfont = hint.font()
        hfont.setPointSize(8)
        hint.setFont(hfont)

        # 第 4 行：大号“删除广告”按钮（突出显示）
        self.delete_btn = QPushButton("删除广告")
        self.delete_btn.setMinimumHeight(36)
        dfont = self.delete_btn.font()
        dfont.setBold(True)
        dfont.setPointSize(11)
        self.delete_btn.setFont(dfont)
        self.delete_btn.setStyleSheet(
            "QPushButton { background-color: #2d7ff9; color: white;"
            " border: none; border-radius: 6px; }"
            "QPushButton:hover { background-color: #1f6cdb; }"
            "QPushButton:pressed { background-color: #1758b8; }"
        )
        self.delete_btn.clicked.connect(self.do_delete)

        # 底部状态栏：只读日志（高度约 6 行）
        self.status_edit = QTextEdit()
        self.status_edit.setReadOnly(True)
        line_height = self.fontMetrics().lineSpacing()
        self.status_edit.setFixedHeight(line_height * 6 + 12)

        main_layout.addLayout(row1)
        main_layout.addLayout(row2)
        main_layout.addLayout(row3)
        main_layout.addWidget(hint)
        main_layout.addWidget(self.delete_btn)
        main_layout.addWidget(self.status_edit, 1)

        self.log("就绪。请选择小说文件、输入检索词，并选择输出目录。")

    def log(self, msg):
        """向状态栏追加一行日志并立即刷新界面。"""
        self.status_edit.append(msg)
        scrollbar = self.status_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        QApplication.processEvents()

    # ------------------------------------------------------------ 选择操作
    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择小说文件", "", "TXT 文件 (*.txt);;所有文件 (*.*)"
        )
        if path:
            self.file_edit.setText(path)
            self.log("已选择文件：" + path)

    def choose_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if directory:
            self.output_edit.setText(directory)
            self.log("已选择输出目录：" + directory)

    def edit_boundary(self):
        """打开“编辑句子分隔符”对话框；保存成功后更新内部正则并即时生效。"""
        dlg = BoundaryDialog(self, self.boundary_pattern, DEFAULT_BOUNDARY_PATTERN)
        if dlg.exec_() == QDialog.Accepted:
            self.boundary_pattern = dlg.get_pattern()
            self._boundary_re = re.compile("(" + self.boundary_pattern + ")", re.IGNORECASE)
            self.log("分隔符已更新：" + self.boundary_pattern)

    # ---------------------------------------------------------------- 检索
    def do_search(self):
        path = self.file_edit.text().strip()
        query = self.query_edit.text().strip()

        # 前置校验
        if not path:
            QMessageBox.critical(self, "错误", "请先选择 TXT 文件。")
            return
        if not query:
            QMessageBox.critical(self, "错误", "请输入检索词。")
            return

        # 读取文件（自动尝试多种编码）
        self.log("正在读取文件...")
        try:
            text, encoding = read_text(path)
        except Exception:
            QMessageBox.critical(
                self, "错误",
                "文件读取失败或编码无法识别。\n请先将文件转换为 UTF-8 编码后重试。",
            )
            return
        self.log("文件读取成功（编码 %s，共 %d 个字符）" % (encoding, len(text)))

        # 拆分句子并逐句匹配（使用当前分隔符正则）
        matcher = parse_query(query)
        sentences = split_sentences(text, self._boundary_re)

        self.log("正在检索...")
        matched = []
        for i, s in enumerate(sentences):
            if matcher(s):
                matched.append(i)
            if i % 20000 == 0:
                QApplication.processEvents()  # 长循环中保持界面响应

        if not matched:
            QMessageBox.warning(self, "提示", "未找到匹配的广告句。")
            return

        # 生成 检索结果.txt 到桌面（UTF-8 带 BOM）
        desktop = get_desktop_dir()
        result_path = os.path.join(desktop, RESULT_FILE_NAME)
        self.log("正在保存检索结果...")
        try:
            lines = ["[%d] %s" % (seq, sentences[i]) for seq, i in enumerate(matched, 1)]
            lines.append("共找到 %d 条广告句" % len(matched))
            write_text(result_path, "\n".join(lines))
        except Exception as e:
            QMessageBox.critical(self, "错误", "写入检索结果失败：%s" % e)
            return

        # 缓存：序号 -> 原始句子索引
        self.sentences = sentences
        self.index_map = {seq: i for seq, i in enumerate(matched, 1)}
        self.source_path = path

        self.log("检索完成，共找到 %d 个广告句，结果已保存至桌面%s" % (len(matched), RESULT_FILE_NAME))
        self.log("可打开该文件手动删除不需要的行，再点击“删除广告”。")

    # ---------------------------------------------------------------- 删除
    def do_delete(self):
        # 前置校验
        if self.sentences is None or self.index_map is None:
            QMessageBox.critical(self, "错误", "请先执行“检索”。")
            return
        output_dir = self.output_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "提示", "请先选择输出目录。")
            return
        if not os.path.isdir(output_dir):
            QMessageBox.critical(self, "错误", "输出目录不存在：%s" % output_dir)
            return

        # 重新读取（可能已被用户手动编辑过的）检索结果文件
        result_path = os.path.join(get_desktop_dir(), RESULT_FILE_NAME)
        try:
            with open(result_path, 'r', encoding='utf-8-sig') as f:
                lines = f.read().splitlines()
        except Exception as e:
            QMessageBox.critical(
                self, "错误", "读取检索结果文件失败：%s\n请重新执行检索。" % e
            )
            return

        # 提取文件中保留的有效序号（跳过空行、总结行、无法解析的行）
        seqs = parse_result_seq_lines(lines)
        # 防御：过滤掉本次检索缓存中不存在的序号
        seqs &= set(self.index_map.keys())

        if not seqs:
            QMessageBox.information(self, "提示", "检索结果文件中未找到有效广告句，无需删除。")
            return

        # 删除前必须确认
        if QMessageBox.question(
            self, "确认", "即将删除 %d 句广告，是否继续？" % len(seqs),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            self.log("已取消删除。")
            return

        # 按“序号 -> 原始句子索引”重建文本：只删除文件中保留下来的行对应的句子
        delete_idx = {self.index_map[seq] for seq in seqs}
        kept = [s for i, s in enumerate(self.sentences) if i not in delete_idx]
        cleaned = "".join(kept)

        # 输出文件：原文件名去广告.txt（保留原扩展名）
        base, ext = os.path.splitext(os.path.basename(self.source_path))
        out_path = os.path.join(output_dir, base + "去广告" + ext)

        # 目标文件已存在时询问是否覆盖
        if os.path.exists(out_path):
            if QMessageBox.question(
                self, "确认", "目标文件已存在：%s\n是否覆盖？" % out_path,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            ) != QMessageBox.Yes:
                self.log("已取消，未覆盖已有文件。")
                return

        self.log("正在保存...")
        try:
            write_text(out_path, cleaned)
        except Exception as e:
            QMessageBox.critical(self, "错误", "保存失败：%s" % e)
            return

        # 删除成功：清空缓存，防止重复删除
        self.sentences = None
        self.index_map = None
        self.source_path = None

        self.log("删除完成，文件已保存至 %s" % out_path)
        self.log("已清空匹配缓存，可重新检索。")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 现代化风格

    # Microsoft YaHei 9pt（缺失时 Qt 自动回退到系统默认字体）
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)

    window = AdCleanerApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
