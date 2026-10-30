# 洛克王国世界图像爬虫

来源：[技能图鉴](https://wiki.biligame.com/nrc/技能图鉴)、[精灵图鉴](https://wiki.biligame.com/nrc/精灵图鉴)。下载原始尺寸图片并保存为PNG。

界面会显示当前图鉴的完整网址，点击即可打开来源页面；切换到精灵头像时自动显示精灵图鉴地址。图片文件来自 `patchwiki.biligame.com`（BWIKI 图片服务）。

## 简单使用
1. 双击 NRCImageCrawler.exe。
2. 默认选择“总爬取（全部四类图像）”，且“缺失爬取”默认开启。直接点击“总爬取”即可。
3. 以后网站有新图像，再打开程序、选择同一个输出根目录、点击“总爬取”，就会只补齐缺少或损坏的图片。已有的有效 PNG 不会重复下载。

图片分别保存在输出根目录下的 `skill`（技能图标）、`skill_type`（技能分类图标）、`element`（系别图标）、`pet`（精灵头像）。默认输出根目录是 exe 所在文件夹。程序每次开始都会重新读取网站清单，不用先手动刷新。

## 范围与模式

| 操作 | 效果 |
| --- | --- |
| 总爬取 + 勾选“缺失爬取”（默认） | 检查全部四类，只补缺少或损坏的图片 |
| 总爬取 + 取消“缺失爬取” | 全量更新四类，所有图片重新下载并覆盖 |
| 选择某个类别或子类 + 勾选“缺失爬取” | 只补当前选择范围内缺少或损坏的图片 |
| 选择某个类别或子类 + 取消“缺失爬取” | 重新下载并覆盖当前范围内全部图片 |

总爬取按钮始终处理全部四类，不受下方子类勾选影响。如果只要 S4 技能，先选择“技能图标”，勾选 S4，再点击“开始爬取当前范围”。搜索名称或勾选子类时，会自动退出“当前类别全部”。

缺失爬取按网页文件名与本地有效 PNG 比对，不检查已有图像的内容更新；想获取同名图标的新版本，请取消“缺失爬取”后再下载。网站下架或名称变化后，旧本地图片会保留，不自动删除。日志会显示各类的网页匹配数、已有跳过数、下载数与失败数；某一类页面失败后仍会尝试其他类别。

## 源码运行与打包

普通使用者只需解压发布压缩包并运行 exe，无需安装 Python。开发者可安装 `requirements.txt` 后运行 `python crawler.py --gui`。

命令行同样默认总爬取并仅补缺失：

```powershell
python crawler.py
python crawler.py --mode full
python crawler.py --dataset skill --season S4
python crawler.py --dataset skill --season S4 --mode full
```

`--preview` 只列出待下载文件，不下载或创建图片目录；`--output` 指定输出根目录。`--all` 表示当前类别全部，而非强制覆盖；强制更新使用 `--mode full`（兼容旧参数 `--overwrite`）。

修改代码后双击 `打包exe.bat`，或运行 `python build_exe.py`。生成的 exe 和包含使用说明及许可证的 zip 位于 `dist/`，将 zip 作为 GitHub Releases 附件发布。

来源：
技能图鉴：https://wiki.biligame.com/nrc/技能图鉴
精灵图鉴：https://wiki.biligame.com/nrc/精灵图鉴
图片文件：patchwiki.biligame.com（BWIKI 图片服务）

下载的游戏图片不在代码许可证授权范围内，其权利归相应权利人所有。
