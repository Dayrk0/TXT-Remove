# 小说TXT广告去除

从 TXT 小说中定位夹杂的广告句，人工复核后生成干净副本。程序只读原文件，清理结果另存为 `原文件名去广告.txt`。

当前版本为 2.0.0，基于 Python + PyQt5，保留原有的“检索 → 复核 → 删除”工作流，并重做了界面、异步检索、编码处理和写入安全。项目根目录同时提供可直接运行的 `小说广告清理工具.exe`。作者/维护：Dayrk0/DSH。

![检索结果（浅色）](docs/screenshots/03-result-light.png)

## 功能

- **句子级检索**：按句号、问号、感叹号、换行、HTML 闭合标签和常见右括号切分句子，再用关键词定位广告句。
- **人工复核**：检索结果写入 `检索结果.txt`，可在记事本中删除不想清理的行；程序按行首序号删除，改句子文字不影响结果。
- **AND / OR 组合**：支持 `网址 OR 公众号`、`网址 AND 关注` 等写法，适合从宽检索再人工收窄。
- **原文件只读**：清理结果始终写入新文件；写入前再次确认，目标文件已存在时单独询问是否覆盖。
- **编码与换行**：优先识别 UTF-8、GBK、GB18030；Big5 与带 BOM 的 UTF-16 为尽力识别。输出可选 UTF-8（带 BOM）、UTF-8、跟随原文件或 GB18030，原换行风格会保留。
- **大文件友好**：检索在后台线程执行，显示进度并可取消，界面不会因十几 MB 的小说卡死。
- **结果预览**：右侧显示命中的前 200 条，关键词高亮；同时提供运行日志和耗时。
- **界面**：浅色/深色主题、拖放文件、查询历史、常用规则、分隔符编辑器和快捷键；设置自动保存。
- **个性化**：设置中可编辑常用规则、调整界面字号（12–20 px，默认 15）；字体固定为 Microsoft YaHei UI，避免排版失控。搜索结果底部使用独立的状态标签，与普通说明文字区分。

## 快速开始

要求 Windows 10/11。项目根目录的 `小说广告清理工具.exe` 可直接双击运行，无需安装 Python。

从源码运行需要 Python 3.9 及以上：

```powershell
cd 小说TXT广告去除
python -m pip install -r requirements.txt
python 小说广告清理工具.py
```

也可以创建独立虚拟环境：

```powershell
python -m venv qt_env
qt_env\Scripts\activate
python -m pip install -r requirements.txt
python 小说广告清理工具.py
```

## 使用流程

1. **选择小说**：拖入或选择一个 `.txt` 文件。窗口会显示大小、编码、字符数和句子数；输出目录默认与小说相同。
2. **输入检索词并检索**：填写广告中稳定出现的词，点击“检索”。程序在桌面生成 `检索结果.txt`，即使 0 条命中也会刷新该文件。
3. **人工复核**：打开 `检索结果.txt`，删除不想清理的行并保存。每行格式为 `[序号] 句子`，序号是删除依据；不需要修改句子内容。
4. **删除并保存**：确认输出目录和编码，点击“删除广告并保存”。程序只删除结果文件中保留序号的句子，生成 `原文件名去广告.txt`，原文件不会被修改。

检索完成后如果原文件被其他程序修改，程序会拒绝删除并要求重新检索，避免按旧索引误删。

右上角“设置”可以编辑常用规则、调整界面字号；字号只影响界面，不改变输出文件编码或正文内容。

### 检索语法

| 写法 | 含义 |
| --- | --- |
| `网址 OR 公众号` | 句子包含任意一个关键词即命中 |
| `网址 AND 关注` | 句子必须同时包含两个关键词 |
| `网址 AND 关注 OR 公众号` | 理解为 `(网址 AND 关注) OR 公众号` |

- `AND`、`OR` 必须大写；小写会被当作普通文字，界面会给出提示。
- 关键词匹配区分大小写，按普通子串匹配，不支持正则或通配符。
- 关键词越短、越稳定，召回越可控；建议先用宽条件检索，再在结果文件中人工删行。

## 输出与安全

- 检索结果：桌面 `检索结果.txt`。可通过环境变量 `TXT_AD_CLEAN_RESULT_DIR` 改变位置（主要用于测试）。
- 清理结果：默认写入小说所在目录，文件名 `原文件名去广告.txt`；若原文件名已含“去广告”，追加 `_clean`，不会覆盖源文件。
- 编码：默认 UTF-8（带 BOM）；也可选择 UTF-8、跟随原文件或 GB18030。
- 换行：保留原文件的 LF、CRLF 或 CR 风格。
- 写入：先写临时文件再原子替换；失败不会留下半截文件。
- 覆盖：保存前确认；目标已存在时再单独询问一次。
- 原文件：全程只读，不执行原地修改。

## 界面

| 浅色 | 深色 |
| --- | --- |
| ![浅色结果](docs/screenshots/03-result-light.png) | ![深色结果](docs/screenshots/04-result-dark.png) |
| ![浅色保存](docs/screenshots/05-saved-light.png) | ![深色保存](docs/screenshots/06-saved-dark.png) |

空状态：[浅色](docs/screenshots/01-empty-light.png)、[深色](docs/screenshots/02-empty-dark.png)。更多截图：[设置](docs/screenshots/09-settings-dialog.png)、[分隔符编辑器](docs/screenshots/07-boundary-dialog.png)、[使用说明](docs/screenshots/08-help-dialog.png)。

界面默认字号为 15 px，可在“设置”中调整到 12–20 px；字体固定为 Microsoft YaHei UI。检索结果底部的状态标签使用独立底色，与说明文字分开。

### 快捷键

| 快捷键 | 操作 |
| --- | --- |
| `Ctrl+O` | 选择小说 |
| `Ctrl+F` | 聚焦检索词 |
| `F5` / `Ctrl+Enter` | 开始检索 |
| `Ctrl+D` | 删除广告并保存 |
| `Ctrl+E` | 编辑句子分隔符 |
| `Ctrl+,` | 打开设置 |
| `F1` | 打开使用说明 |
| `Esc` | 取消当前检索 |

## 项目结构

```text
小说TXT广告去除/
├─ 小说广告清理工具.py        # 主程序（PyQt5）
├─ 小说广告清理工具.exe       # 本地打包的单文件程序（不提交仓库）
├─ adclean_core.py            # 与界面无关的文本处理核心
├─ requirements.txt
├─ requirements-dev.txt       # PyInstaller 等开发依赖
├─ README.md
├─ assets/
│  ├─ app.ico                 # 程序图标
│  ├─ app-256.png             # 图标预览
│  └─ version_info.txt        # exe 作者与版本信息
├─ scripts/
│  └─ build_exe.ps1           # 一键打包脚本
├─ docs/
│  ├─ README-v1.txt           # 1.x 项目记录（保留）
│  ├─ 开发记录.md             # 版本演进与设计说明
│  ├─ prompt1-初始需求.txt
│  ├─ prompt2-改进.txt
│  ├─ prompt3-改进规则.txt
│  ├─ prompt4-进一步优化.txt
│  └─ screenshots/            # 2.0 界面截图
├─ legacy/
│  └─ 小说广告清理工具_tkinter.py
├─ tests/
│  ├─ test_core.py
│  └─ test_gui.py
├─ 已处理小说/                # 已清理的成品样本，单独存放
└─ 小说原文/                  # 原始小说样本，本地保留，不纳入仓库
```

`已处理小说/` 中的三个成品用于回归和手工比对；`小说原文/` 体积较大，已在 `.gitignore` 中排除。`qt_env/` 是本地虚拟环境，同样不提交。

## 测试

```powershell
python -m unittest discover -s tests -v
```

- 38 个测试：29 个核心文本处理测试 + 9 个 PyQt5 离屏集成测试。
- GUI 测试覆盖检索、结果文件、删除、源文件变更保护、编辑检索结果、GBK 跟随原编码、分隔符对话框、使用说明、默认字号/状态标签和设置对话框。
- 测试默认 `QT_QPA_PLATFORM=offscreen`，无显示器环境也能运行；GUI 测试的临时目录位于 `tests/_tmp/`，核心测试使用标准库临时目录。

## 打包

```powershell
python -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
```

脚本使用 PyInstaller 生成单文件、无控制台窗口的 `小说广告清理工具.exe`，直接放在项目根目录；中间文件写入 `build/`。`.exe`、`build/` 和运行期临时目录 `_MEI*/` 都已加入 `.gitignore`，仓库只保留源码、图标、版本信息和打包脚本，不提交二进制。首次在干净机器上运行时建议先做一次完整检索和保存测试。

打包时会写入 `assets/version_info.txt` 中的作者/产品信息（CompanyName 为 `Dayrk0/DSH`），并设置 `--runtime-tmpdir "."`，让 PyInstaller 在程序所在工作目录解压，而不是依赖 `%TEMP%`。这可以避开 Windows 11 对临时目录的权限/安全软件拦截所导致的 `Could not create temporary directory`；程序正常退出时会自动清理 `_MEI*` 目录。运行时请把 exe 放在可写目录（不要放进 `Program Files` 等只读位置），否则本地解压仍会失败。首次运行仍可能出现 SmartScreen“未知发布者”提示，这是未做受信任代码签名的正常现象，点击“更多信息 → 仍要运行”即可；要彻底去掉该提示需要购买并配置受信任的代码签名证书。

也可以手动执行：

```powershell
python -m PyInstaller --noconfirm --clean --onefile --windowed `
  --name 小说广告清理工具 --icon "$PWD\assets\app.ico" `
  --version-file "$PWD\assets\version_info.txt" --runtime-tmpdir "." `
  --distpath . --workpath build\pyinstaller --specpath build `
  小说广告清理工具.py
```

## 设置

设置保存在 `%APPDATA%\TXTAdCleaner\settings.ini`，包含主题、窗口位置、查询历史、常用规则、界面字号、输出编码、分隔符和最近目录。删除该文件即可恢复默认。测试或便携场景可用 `TXT_AD_CLEAN_SETTINGS_DIR` 指定其他目录。

“设置”中可编辑常用规则、字号（12–20 px）；字体固定为 Microsoft YaHei UI，不提供字体切换，避免不同机器上的排版差异。常用规则只影响检索词的快捷填充，不会自动执行检索或删除。

## 常见问题

**检索结果文件在哪里？**  
默认在桌面。旧版工作流依赖桌面文件，2.0 仍保持这个位置，便于用记事本复核。

**为什么没有命中？**  
先确认 `AND` / `OR` 是大写，关键词区分大小写；再换更短、更稳定的词，例如 `http`、`公众号`、`求书`。不要直接输入整句广告。

**为什么删除按钮是灰的？**  
需要先完成一次有命中的检索；修改分隔符、换文件或保存成功后，旧索引会失效，必须重新检索。

**能直接覆盖原文件吗？**  
不能。程序只生成副本，原文件全程只读。

**打开后中文乱码怎么办？**  
用记事本或 VS Code 将文件另存为 UTF-8 后重试。Big5 和部分 UTF-16 文件为尽力识别，不能保证所有文件都正确。

**支持 macOS / Linux 吗？**  
代码本身使用跨平台库，但当前只在 Windows 10/11 上验证；深色标题栏等细节仅在 Windows 生效。

## 版本说明

### 2.0.0

- 重做 PyQt5 界面：浅色/深色主题、卡片式布局、拖放、空状态、结果预览与运行日志。
- 检索改为后台线程，带进度和取消；大文件不再阻塞窗口。
- 增加查询历史、常用规则、快捷键、分隔符实时校验和使用说明。
- 新增设置对话框：可编辑常用规则、调整 12–20 px 界面字号；字体固定，配置持久化。
- 搜索结果底部改为独立状态标签；其余说明文字压缩为一句，详细说明集中到 README / 使用说明。
- 提供 `小说广告清理工具.exe` 和 `scripts/build_exe.ps1`，源码与构建产物分离。
- 增强 TXT 处理：更多编码、原换行保留、输出编码选择、句子空白合并、结果文件不产生空行、0 命中时刷新旧结果。
- 强化写入安全：源文件变更检测、原子写入、覆盖确认、输出命名避让。
- 拆分 `adclean_core.py`，补充 38 个测试、项目整理和文档。

### 1.x

历史版本、提示词迭代过程和原始分享链接见 [README-v1.txt](docs/README-v1.txt) 与 [开发记录.md](docs/开发记录.md)。

## 说明

本项目用于个人文本整理。请仅处理自己有权使用的文本；程序不联网，所有处理都在本机完成。
