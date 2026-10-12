# 洛克王国世界图像爬虫

来源：[技能图鉴](https://wiki.biligame.com/nrc/技能图鉴)、[精灵图鉴](https://wiki.biligame.com/nrc/精灵图鉴)。下载原始尺寸图片并保存为真正的 PNG，保留透明通道，不需要手动重命名。

界面会显示当前图鉴的完整网址，点击即可打开来源页面；切换到精灵头像时自动显示精灵图鉴地址。图片文件来自 `patchwiki.biligame.com`（BWIKI 图片服务），命令行也会打印来源地址。

## 图片目录与命名

默认在本文件夹下生成四个目录，也可选择其他输出根目录，程序仍按以下名称分类保存。

| 目录 | 内容 | 文件名示例 |
| --- | --- | --- |
| `skill` | 技能图标 | `星火.png`、`麦芒.png` |
| `skill_type` | 物攻、魔攻、防御、状态四个分类图标 | `物攻.png`、`防御.png` |
| `element` | 普通、草、火、水等系别图标 | `普通.png`、`火.png` |
| `pet` | 精灵图鉴“紧凑”模式的头像 | `011鸭吉吉（急急急鸭）.png`、`007烈火战神.png` |

精灵文件名由 **编号 + 名称 + （形态）** 组成：保留编号的前导零，使用中文全角括号；形态为空或为“首领形态”时省略括号和形态，例如 `001迪莫.png`、`007烈火战神.png`。保留其他形态的完整名称，包括“本来的样子”。

“紧凑”模式显示的是头像，不是“卡片”模式的立绘。网页 HTML 本身包含这套头像，因此程序直接提取紧凑模式使用的 `.npc-art-head` 原图，无需启动浏览器或点击按钮。

原有 `output` 技能图片目录已迁移为 `skill`。`--output` 现在表示**输出根目录**，例如 `--output "D:\图像" --dataset pet` 保存到 `D:\图像\pet`。

## 安装与勾选界面

首次安装依赖，在本文件夹打开终端运行：

```powershell
python -m pip install -r requirements.txt
```

双击 `启动技能图标爬虫.bat`，或运行：

```powershell
python crawler.py --gui
```

在“图片种类”中切换技能图标、技能分类图标、系别图标、精灵头像。界面显示当前网站筛选条件、匹配文件名预览和实际保存目录。

页面右侧的滚动条可查看下方预览和日志，也可在筛选区域使用鼠标滚轮。预览区域保留独立滚动条和至少 300 像素的显示高度，文件名列表不会被筛选条件挤压。

- 技能默认只勾选 **S4**，可按赛季、属性、分类、标签、近期调整筛选。
- 技能分类和系别默认勾选全部选项，可取消不需要的选项。
- 精灵可按赛季、系别、主形态/地区形态/首领形态、进化阶段筛选，也可搜索名称或编号。下载全部精灵需明确勾选“全量爬取”。
- 同组多选取并集，不同组取交集；清空所有条件不会自动变为全量。
- 下载期间锁定筛选和输出目录，避免界面修改与实际下载任务不一致。
- 重复运行跳过有效的已有 PNG；损坏图片会重新下载。勾选“重新下载已有图片”可刷新。
- 点击“停止”后会结束当前请求，再次运行可继续；下载失败逐张记录，不影响其他图片。
- “刷新网站数据”可读取最新图鉴或在网络失败后重试。
- 字段缺失、筛选无效、文件名冲突时会报错，不会自动退回全量。Windows 文件名不允许的字符替换为 `_`。

## 命令行

下载 S4 技能图标、四个分类图标和全部系别图标：

```powershell
python crawler.py --season S4
python crawler.py --dataset skill_type --all
python crawler.py --dataset element --all
```

下载全部精灵头像，或只下载 S4 精灵：

```powershell
python crawler.py --dataset pet --all
python crawler.py --dataset pet --season S4
```

按精灵编号、名称、形态类型筛选：

```powershell
python crawler.py --dataset pet --number 011
python crawler.py --dataset pet --keyword "鸭吉吉（急急急鸭）"
python crawler.py --dataset pet --number 007 --pet-form lord
python crawler.py --dataset pet --element 火 --stage 1
```

指定图标选项、组合技能筛选、指定输出根目录：

```powershell
python crawler.py --dataset skill_type --name 物攻 --name 防御
python crawler.py --dataset element --name 火 --name 水
python crawler.py --season S3 --season S4 --element 火 --output "D:\图像"
```

仅查看条件或预览文件名：

```powershell
python crawler.py --list-filters
python crawler.py --dataset pet --list-filters
python crawler.py --dataset pet --season S4 --preview
```

`--all` 表示当前图片种类的全量；`--overwrite` 强制重新下载；`--delay` 控制图片请求间隔，默认 0.4 秒。筛选参数可重复指定，不支持当前图片种类的参数会直接报错。

当前网站（2026-10-12）：579 个技能，其中 S4 为 26 个；4 个技能分类图标；18 个系别图标；625 张精灵紧凑头像，其中 S4 为 50 张。以每次读取到的网站数据为准。

## 验证

```powershell
python -m unittest discover -s tests -v
```

## 开源协议与图片来源

本项目代码与文档采用 [MIT License](LICENSE)，允许使用、修改和分发，需保留许可证与版权声明。

下载的游戏图标、精灵头像及其他第三方网站内容不在本项目 MIT 授权范围内，其权利归相应权利人所有；本项目的代码许可证不授予这些素材的使用或分发权。

## 发布到 GitHub

### 打包 Windows exe

打包者需要 Windows 和 Python 3.10 或更高版本。在本文件夹双击 `打包exe.bat`，或运行：

```powershell
python build_exe.py
```

脚本会创建隔离的 `.venv-build` 环境，安装依赖与 PyInstaller，运行测试，再生成单文件、无控制台窗口的 GUI 程序。首次打包需要联网安装依赖。构建完成后自动检查 exe 内置的 Tk、图片读写、网页解析和 HTTPS 证书，以及默认输出路径。

生成文件：

- `dist/NRCImageCrawler.exe`：双击直接打开界面，使用者无需安装 Python。
- `dist/NRCImageCrawler-windows-amd64.zip`：包含 exe、使用说明和 MIT 许可证，适合上传到 GitHub Releases；文件名的架构后缀以打包环境为准。

exe 默认将图片保存到自身所在目录下的 `skill`、`skill_type`、`element`、`pet`，不会写入 PyInstaller 的临时解压目录。可在界面更改输出根目录。请将程序放在自己有写入权限的文件夹；首次启动需要等待内置环境解压，下载仍需网络连接。生成的 exe 适用于打包机器对应的 Windows 架构。

发布时将 zip 上传到 GitHub Release 的附件。`build/`、`dist/`、`.venv-build/` 已被 Git 忽略，不随源码提交。

将 `nrc_skill_crawler` 作为独立仓库根目录，提交代码、测试、`requirements.txt`、启动脚本、`README.md`、`LICENSE` 和 `.gitignore`。

`.gitignore` 已排除四个图片目录、旧 `output` 目录、Python 缓存、虚拟环境、临时下载、日志和本地配置。下载的图片会保留在电脑上，但不会随新提交上传到 GitHub。若图片之前已经被 Git 跟踪，需要额外移出 Git 索引；新增忽略规则不会取消已有跟踪。
