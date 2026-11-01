# -*- coding: utf-8 -*-
"""
小说广告清理工具
================
从 TXT 小说文件中查找并删除广告语句的桌面 GUI 工具。

- 界面：Tkinter（Python 标准库），无任何第三方依赖
- 运行：python 本文件.py （Windows 下可直接双击）
- 打包：pyinstaller --onefile --windowed --name 小说广告清理工具 本文件.py

注意：本程序不依赖 __file__ 定位任何资源文件，打包后行为与源码运行一致。
"""

import os
import re
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox

# 句子边界：中英文句号、问号、感叹号、换行符。
# 使用零宽后行断言 (?<=...) 拆分，分隔符保留在句末，方便整句删除后原样拼接。
SENTENCE_BOUNDARY = re.compile(r'(?<=[。！？!?\n])')

# 读取文件时依次尝试的编码顺序
ENCODINGS = ('utf-8-sig', 'gbk', 'gb18030')


def parse_query(query):
    """
    解析检索表达式，返回一个函数：输入句子，返回该句子是否匹配。

    逻辑：
        - 以 ' OR ' 为分隔符，将表达式拆分成多个"与组"；
        - 每组内再用 ' AND ' 拆分成多个词；
        - 句子只要满足"任意一个与组"（组内所有词都出现在句中）即视为匹配。
    示例：
        "小说 AND 广告 OR 网址"   -> 匹配"小说+广告"或"网址"
        "广告 OR 无弹窗 AND 清爽" -> 匹配"广告"或"无弹窗+清爽"
    若表达式中不含 AND / OR，则整体视为单个检索词。
    """
    def build_group_matcher(group):
        # 组内按 AND 拆分，过滤空白词，避免出现 "" in 句子 恒为真的问题
        words = [w for w in group.split(' AND ') if w]
        return lambda sent: all(w in sent for w in words)

    # 按 OR 拆分，过滤空白组
    or_groups = [g for g in query.split(' OR ') if g.strip()]
    group_matchers = [build_group_matcher(g) for g in or_groups]

    def match(sentence):
        return any(m(sentence) for m in group_matchers)

    return match


def read_text(path):
    """
    按 ENCODINGS 顺序尝试读取文件，返回 (文本, 实际使用的编码)。
    全部编码均失败时抛出最后一次 UnicodeDecodeError。
    """
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
    """返回桌面目录；若不存在（如某些精简系统），回退到用户主目录。"""
    desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    return desktop if os.path.isdir(desktop) else os.path.expanduser('~')


class AdCleanerApp:
    """主窗口界面与业务逻辑。"""

    def __init__(self, root):
        self.root = root
        root.title("小说广告清理工具")
        root.geometry("680x280")
        root.minsize(560, 240)

        # 界面变量
        self.file_var = tk.StringVar()      # 所选文件路径
        self.query_var = tk.StringVar()     # 检索表达式
        self.overwrite_var = tk.BooleanVar(value=False)  # 是否覆盖原文件

        # 内部数据缓存（供"删除广告"按钮使用）
        self.sentences = None    # 拆分后的句子元素列表
        self.matched_idx = None  # 命中的广告句下标集合
        self.matched_count = 0   # 命中数量
        self.source_path = None  # 检索时使用的源文件路径

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # 第 1 行：文件选择
        file_frame = tk.Frame(self.root)
        file_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        tk.Label(file_frame, text="文件：").pack(side=tk.LEFT)
        self.file_entry = tk.Entry(file_frame, textvariable=self.file_var, state="readonly")
        self.file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(file_frame, text="浏览", command=self.choose_file).pack(side=tk.LEFT)

        # 第 2 行：检索词输入
        query_frame = tk.Frame(self.root)
        query_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(query_frame, text="检索词：").pack(side=tk.LEFT)
        self.query_entry = tk.Entry(query_frame, textvariable=self.query_var, width=50)
        self.query_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(query_frame, text="检索", command=self.do_search).pack(side=tk.LEFT)

        # 第 3 行：删除按钮 + 覆盖原文件复选框
        action_frame = tk.Frame(self.root)
        action_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Button(action_frame, text="删除广告", command=self.do_delete).pack(side=tk.LEFT)
        tk.Checkbutton(
            action_frame, text="覆盖原文件（自动备份 .bak）",
            variable=self.overwrite_var,
        ).pack(side=tk.LEFT, padx=10)

        # 第 4 行：状态栏（只读多行日志）
        self.status_text = tk.Text(self.root, height=3, state="disabled", wrap="word")
        self.status_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        self.log("就绪。请选择小说文件并输入检索词。")
        self.log("提示：检索词可用 AND / OR 组合，如“小说 AND 广告 OR 网址”。")

    def log(self, msg):
        """向状态栏追加一行日志并立即刷新界面。"""
        self.status_text.config(state="normal")
        self.status_text.insert(tk.END, msg + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state="disabled")
        self.root.update()

    # ------------------------------------------------------------ 文件选择
    def choose_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("TXT 文件", "*.txt"), ("所有文件", "*.*")]
        )
        if path:
            self.file_var.set(path)
            self.log("已选择文件：" + path)

    # ---------------------------------------------------------------- 检索
    def do_search(self):
        path = self.file_var.get().strip()
        query = self.query_var.get().strip()

        # 前置校验
        if not path:
            messagebox.showerror("错误", "请先选择 TXT 文件。")
            return
        if not query:
            messagebox.showerror("错误", "请输入检索词。")
            return

        # 读取文件（自动尝试多种编码）
        self.log("正在读取文件...")
        try:
            text, encoding = read_text(path)
        except Exception:
            messagebox.showerror(
                "错误",
                "文件读取失败或编码无法识别。\n请先将文件转换为 UTF-8 编码后重试。",
            )
            return
        self.log("文件读取成功（编码 %s，共 %d 个字符）" % (encoding, len(text)))

        # 拆分句子并逐句匹配
        matcher = parse_query(query)
        sentences = SENTENCE_BOUNDARY.split(text)

        self.log("正在检索...")
        matched = [i for i, s in enumerate(sentences) if matcher(s)]
        if not matched:
            messagebox.showerror("提示", "未找到匹配的广告句。")
            return

        # 将结果写入桌面 检索结果.txt（UTF-8 带 BOM）
        desktop = get_desktop_dir()
        result_path = os.path.join(desktop, "检索结果.txt")
        self.log("正在保存检索结果...")
        try:
            lines = ["[%d] %s" % (idx + 1, sentences[i]) for idx, i in enumerate(matched)]
            lines.append("共找到 %d 条广告句" % len(matched))
            write_text(result_path, "\n".join(lines))
        except Exception as e:
            messagebox.showerror("错误", "写入检索结果失败：%s" % e)
            return

        # 缓存匹配结果，供"删除广告"按钮使用
        self.sentences = sentences
        self.matched_idx = set(matched)
        self.matched_count = len(matched)
        self.source_path = path

        self.log("检索完成，共找到 %d 个广告句，结果已保存至桌面检索结果.txt" % self.matched_count)

    # ---------------------------------------------------------------- 删除
    def do_delete(self):
        if self.matched_idx is None:
            messagebox.showerror("错误", "请先执行“检索”。")
            return

        # 删除前必须确认
        if not messagebox.askyesno("确认", "即将删除 %d 句广告，是否继续？" % self.matched_count):
            self.log("已取消删除。")
            return

        # 重建文本：跳过所有命中的广告句元素（分隔符保留在句末，整句一并丢弃）
        kept = [s for i, s in enumerate(self.sentences) if i not in self.matched_idx]
        cleaned = "".join(kept)

        base, ext = os.path.splitext(self.source_path)
        try:
            self.log("正在保存...")
            if self.overwrite_var.get():
                # 覆盖原文件：先自动备份为 原文件名.bak
                bak_path = base + ".bak"
                shutil.copy2(self.source_path, bak_path)
                self.log("备份完成：%s" % bak_path)
                write_text(self.source_path, cleaned)
                save_path = self.source_path
            else:
                # 默认另存为 原文件名_clean.txt，不动原文件
                save_path = base + "_clean" + ext
                write_text(save_path, cleaned)
        except Exception as e:
            messagebox.showerror("错误", "保存失败：%s" % e)
            return

        # 删除成功：清空匹配缓存，防止重复删除
        self.sentences = None
        self.matched_idx = None
        self.matched_count = 0
        self.source_path = None

        self.log("删除完成，文件已保存至 %s" % save_path)
        self.log("已清空匹配缓存，可重新检索。")


def main():
    root = tk.Tk()
    AdCleanerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
