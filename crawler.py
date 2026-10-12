"""Download NRC skill, category, element and compact pet icons."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
import re
import sys
import threading
import time
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from PIL import Image

CATALOG_URL = "https://wiki.biligame.com/nrc/%E6%8A%80%E8%83%BD%E5%9B%BE%E9%89%B4"
PET_CATALOG_URL = "https://wiki.biligame.com/nrc/%E7%B2%BE%E7%81%B5%E5%9B%BE%E9%89%B4"
DEFAULT_OUTPUT = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
                  else Path(__file__).resolve().parent)
DATASET_LABELS = {"skill": "技能图标", "skill_type": "技能分类图标",
                  "element": "系别图标", "pet": "精灵头像（紧凑模式）"}
FILTER_FIELDS = {"season": "season", "element": "type", "category": "category",
                 "tag": "tag", "recent": "recent"}
FILTER_LABELS = {"season": "赛季", "element": "属性", "category": "分类",
                 "tag": "标签", "recent": "近期调整", "name": "图标选项",
                 "form_kind": "形态类型", "stage": "进化阶段", "number": "编号"}
PET_GROUPS = {"season": "season", "element": "type", "form_kind": "form", "stage": "stage"}
OPTION_LABELS = {"main": "主形态", "regional": "地区形态", "lord": "首领形态",
                 "none": "非赛季限定", "1": "一阶", "2": "二阶", "3": "三阶"}


@dataclass(frozen=True)
class Icon:
    name: str
    image_url: str


@dataclass(frozen=True)
class Pet:
    number: str
    pet_name: str
    form: str
    image_url: str
    season: tuple[str, ...]
    element: tuple[str, ...]
    form_kind: tuple[str, ...]
    stage: str

    @property
    def name(self) -> str:
        suffix = f"（{self.form}）" if self.form and self.form != "首领形态" else ""
        return f"{self.number}{self.pet_name}{suffix}"


@dataclass(frozen=True)
class Skill:
    name: str
    image_url: str
    season: str
    element: str
    category: str
    tags: tuple[str, ...]
    recent: str


@dataclass
class Catalog:
    skills: list[Skill | Icon | Pet]
    options: dict[str, list[str]]
    icons: dict[str, list[Icon]] = field(default_factory=dict)


@dataclass
class Selection:
    season: list[str] = field(default_factory=list)
    element: list[str] = field(default_factory=list)
    category: list[str] = field(default_factory=list)
    tag: list[str] = field(default_factory=list)
    recent: list[str] = field(default_factory=list)
    keyword: str = ""
    all_skills: bool = False


def original_image_url(src: str) -> str:
    """MediaWiki thumbnail paths include a size suffix; use the original asset."""
    parts = urlsplit(urljoin(CATALOG_URL, src))
    path = parts.path
    if "/thumb/" in path:
        path = path.replace("/thumb/", "/", 1).rsplit("/", 1)[0]
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


def parse_catalog(html: str) -> Catalog:
    soup = BeautifulSoup(html, "html.parser")
    options = {}
    for key, suffix in FILTER_FIELDS.items():
        attr = f"data-skill-catalog-{suffix}"
        options[key] = list(dict.fromkeys(
            node[attr] for node in soup.select(f".nrc-skill-catalog-filter-option[{attr}]")
            if node[attr]
        ))
    skills = []
    seen = {}
    for card in soup.select(".nrc-skill-catalog-card"):
        name_node = card.select_one(".nrc-skill-catalog-card-name")
        icon = card.select_one(".nrc-skill-catalog-card-icon img")
        name = name_node.get_text(strip=True) if name_node else ""
        src = (icon.get("src") or icon.get("data-src")) if icon else None
        if not name or not src:
            raise ValueError("技能卡片缺少名称或图标；网站结构可能已改变。")
        values = [str(card.get(f"data-skill-catalog-{key}", "")).strip()
                  for key in ("season", "type", "category", "recent")]
        if not all(values):
            raise ValueError(f"技能「{name}」缺少筛选字段；停止以免误爬全量。")
        skill = Skill(name, original_image_url(src), values[0], values[1], values[2],
                      tuple(filter(None, str(card.get("data-skill-catalog-tags", "")).split("|"))),
                      values[3])
        if name in seen:
            if seen[name] != skill:
                raise ValueError(f"存在不同的同名技能「{name}」，无法安全按名称保存。")
            continue
        seen[name] = skill
        skills.append(skill)
    if not skills:
        raise ValueError("未找到技能卡片，可能是网络验证页或网站结构已改变。")
    # Keep selection available even if the site removes the filter controls.
    for key in FILTER_FIELDS:
        if not options[key]:
            options[key] = list(dict.fromkeys(
                value for skill in skills
                for value in (skill.tags if key == "tag" else [getattr(skill, key)])
            ))
    icons = {}
    for dataset, suffix in (("skill_type", "category"), ("element", "type")):
        attr = f"data-skill-catalog-{suffix}"
        items = []
        for node in soup.select(f".nrc-skill-catalog-filter-option[{attr}]"):
            image = node.select_one("img")
            if image and image.get("src"):
                items.append(Icon(node[attr], original_image_url(image["src"])))
        icons[dataset] = items
    return Catalog(skills, options, icons)


def parse_pet_catalog(html: str) -> Catalog:
    soup = BeautifulSoup(html, "html.parser")
    pets = []
    for card in soup.select(".npc-card"):
        number_node = card.select_one(".npc-number")
        name_node = card.select_one(".npc-name")
        form_node = card.select_one(".npc-form")
        image = card.select_one(".npc-art-head img")  # The image shown in compact mode.
        number = number_node.get_text(strip=True) if number_node else ""
        name = name_node.get_text(strip=True) if name_node else ""
        src = (image.get("src") or image.get("data-src")) if image else None
        if not number.isdecimal() or not name or not src:
            raise ValueError("精灵卡片缺少编号、名称或紧凑头像；网站结构可能已改变。")
        def tokens(key):
            return tuple(filter(None, str(card.get(f"data-{key}", "")).split("|")))
        pet = Pet(number.zfill(3), name, form_node.get_text(strip=True) if form_node else "",
                  original_image_url(src), tokens("season"), tokens("type"), tokens("form"),
                  str(card.get("data-stage", "")))
        if not pet.season or not pet.element or not pet.form_kind:
            raise ValueError(f"精灵「{pet.name}」缺少筛选字段。")
        pets.append(pet)
    if not pets:
        raise ValueError("未找到精灵紧凑头像，可能是网络验证页或网站结构已改变。")
    output_paths(pets, Path("pet"))  # Detect collisions after omitting the lord suffix.
    options = {}
    for key, group in PET_GROUPS.items():
        options[key] = list(dict.fromkeys(
            node.get("data-value") for node in soup.select(".npc-filter-chip")
            if node.get("data-group") == group and node.get("data-value")
        ))
        for pet in pets:
            for value in item_values(pet, key):
                if value and value not in options[key]:
                    options[key].append(value)
    return Catalog(pets, options)


def item_values(item, key: str) -> tuple[str, ...]:
    value = item.tags if key == "tag" else getattr(item, key)
    return tuple(value) if isinstance(value, (tuple, list)) else (value,)


def select_items(catalog: Catalog, filters: dict[str, list[str]], *, keyword="", all_items=False):
    has_filters = any(filters.values()) or bool(keyword.strip())
    if all_items and has_filters:
        raise ValueError("全量爬取不能与其他筛选条件同时使用。")
    if not all_items and not has_filters:
        raise ValueError("请至少勾选一个筛选条件，或明确选择全量爬取。")
    for key, values in filters.items():
        if key == "number":
            if any(not value.isdecimal() for value in values):
                raise ValueError("精灵编号必须为数字。")
            continue
        invalid = set(values) - set(catalog.options.get(key, []))
        if invalid:
            raise ValueError(f"未知{FILTER_LABELS.get(key, key)}：{'、'.join(sorted(invalid))}")
    return [item for item in catalog.skills
            if all(not values or set(values).intersection(item_values(item, key))
                   for key, values in filters.items())
            and keyword.strip().casefold() in item.name.casefold()]


def select_skills(catalog: Catalog, selection: Selection) -> list[Skill]:
    has_filters = any(getattr(selection, key) for key in FILTER_FIELDS) or bool(selection.keyword.strip())
    if selection.all_skills and has_filters:
        raise ValueError("全量爬取不能与其他筛选条件同时使用。")
    if not selection.all_skills and not has_filters:
        raise ValueError("请至少勾选一个筛选条件（例如 S4），或明确选择全量爬取。")
    for key in FILTER_FIELDS:
        invalid = set(getattr(selection, key)) - set(catalog.options[key])
        if invalid:
            raise ValueError(f"未知{FILTER_LABELS[key]}：{'、'.join(sorted(invalid))}")
    result = []
    for skill in catalog.skills:
        if any(getattr(selection, key) and not (
            set(selection.tag).intersection(skill.tags) if key == "tag"
            else getattr(skill, key) in getattr(selection, key)
        ) for key in FILTER_FIELDS):
            continue
        if selection.keyword.strip().casefold() not in skill.name.casefold():
            continue
        result.append(skill)
    return result


def filename_for(name: str) -> str:
    # Windows rejects control characters, reserved characters, and device names.
    clean = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", name).strip().rstrip(". ")
    if not clean:
        raise ValueError(f"名称无法用作文件名：{name!r}")
    if re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])", clean.split(".")[0]):
        clean = "_" + clean
    return clean + ".png"


def output_paths(skills, output: Path) -> list[Path]:
    paths = [output / filename_for(skill.name) for skill in skills]
    counts = Counter(path.name.casefold() for path in paths)
    duplicate = [name for name, count in counts.items() if count > 1]
    if duplicate:
        raise ValueError(f"名称清理后发生文件名冲突：{'、'.join(duplicate)}")
    return paths


def valid_png(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            if image.format != "PNG":
                return False
            image.verify()
        return True
    except (OSError, ValueError, SyntaxError):
        return False


def new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                            "Referer": CATALOG_URL})
    return session


def fetch_bytes(session, url: str) -> bytes:
    for attempt in range(3):
        try:
            response = session.get(url, timeout=(10, 30))
            response.raise_for_status()
            return response.content
        except requests.RequestException as error:
            status = error.response.status_code if error.response is not None else None
            if attempt == 2 or (status is not None and status < 500 and status != 429):
                raise
            time.sleep(attempt + 1)
    raise RuntimeError("下载重试失败")


def fetch_catalog(session) -> Catalog:
    return parse_catalog(fetch_bytes(session, CATALOG_URL).decode("utf-8-sig"))


def fetch_dataset(session, dataset: str) -> Catalog:
    if dataset == "pet":
        return parse_pet_catalog(fetch_bytes(session, PET_CATALOG_URL).decode("utf-8-sig"))
    catalog = fetch_catalog(session)
    if dataset == "skill":
        return catalog
    icons = catalog.icons[dataset]
    if not icons or len(icons) != len(catalog.options["category" if dataset == "skill_type" else "element"]):
        raise ValueError("选项图标缺失，网站结构可能已改变。")
    return Catalog(icons, {"name": [icon.name for icon in icons]})


def download_icons(skills, output: Path, session, *, overwrite=False,
                   delay=0.4, log=print, stop: threading.Event | None = None) -> dict[str, int]:
    paths = output_paths(skills, output)  # Check every name before writing any file.
    output.mkdir(parents=True, exist_ok=True)
    counts = {"saved": 0, "skipped": 0, "failed": 0}
    for index, (skill, path) in enumerate(zip(skills, paths), 1):
        if stop and stop.is_set():
            log("已停止，可再次运行继续下载。")
            break
        if not overwrite and valid_png(path):
            counts["skipped"] += 1
            log(f"[{index}/{len(skills)}] 已存在：{path.name}")
            continue
        temp = path.with_suffix(".png.part")
        try:
            content = fetch_bytes(session, skill.image_url)
            # Decode the actual response, so an HTML error cannot become a .png file.
            with Image.open(BytesIO(content)) as image:
                image.load()
                image.convert("RGBA").save(temp, format="PNG")
            temp.replace(path)
            counts["saved"] += 1
            log(f"[{index}/{len(skills)}] 已保存：{path.name}")
        except (requests.RequestException, OSError, ValueError, SyntaxError) as error:
            counts["failed"] += 1
            log(f"[{index}/{len(skills)}] 失败：{skill.name}：{error}")
        finally:
            temp.unlink(missing_ok=True)
        if delay and index < len(skills):
            if stop:
                stop.wait(delay)
            else:
                time.sleep(delay)
    log(f"新增 {counts['saved']}，跳过 {counts['skipped']}，失败 {counts['failed']}。目录：{output}")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="下载技能、技能分类、系别图标和精灵紧凑头像")
    parser.add_argument("--gui", action="store_true", help="打开勾选界面")
    parser.add_argument("--dataset", choices=list(DATASET_LABELS), default="skill", help="图片种类")
    for key in FILTER_FIELDS:
        parser.add_argument(f"--{key}", action="append", default=[], help=f"{FILTER_LABELS[key]}；可重复指定")
    parser.add_argument("--name", action="append", default=[], help="分类或系别图标名称，可重复指定")
    parser.add_argument("--pet-form", action="append", default=[], choices=["main", "regional", "lord"])
    parser.add_argument("--stage", action="append", default=[], choices=["1", "2", "3"])
    parser.add_argument("--number", action="append", default=[], help="精灵编号，可重复指定")
    parser.add_argument("--keyword", default="", help="名称包含的文字")
    parser.add_argument("--all", dest="all_skills", action="store_true", help="明确下载全量")
    parser.add_argument("--list-filters", action="store_true", help="仅查看当前图片种类的可用筛选条件")
    parser.add_argument("--preview", action="store_true", help="仅列出匹配文件名，不下载图片")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="输出根目录，在其下创建 skill/skill_type/element/pet")
    parser.add_argument("--overwrite", action="store_true", help="重新下载已有图片")
    parser.add_argument("--delay", type=float, default=0.4, help="图片请求间隔秒数")
    args = parser.parse_args()
    if args.gui:
        from gui import run_gui
        run_gui(args.output)
        return 0
    if args.delay < 0:
        parser.error("--delay 不能小于 0")
    allowed = (set(FILTER_FIELDS) if args.dataset == "skill" else
               set(PET_GROUPS) | {"number"} if args.dataset == "pet" else {"name"})
    filters = {key: getattr(args, key) for key in FILTER_FIELDS}
    filters.update(name=args.name, form_kind=args.pet_form, stage=args.stage,
                   number=[number.zfill(3) for number in args.number])
    unsupported = [key for key, values in filters.items() if values and key not in allowed]
    if unsupported:
        parser.error(f"{args.dataset} 不支持这些筛选：{'、'.join(unsupported)}")
    filters = {key: values for key, values in filters.items() if key in allowed}
    if not args.list_filters and not args.all_skills and not (any(filters.values()) or args.keyword.strip()):
        parser.error("请选择 --season S4 等筛选条件；也可以用 --gui 打开勾选界面")
    try:
        with new_session() as session:
            print(f"下载来源（BWIKI）：{unquote(PET_CATALOG_URL if args.dataset == 'pet' else CATALOG_URL)}")
            print("图片文件来源：patchwiki.biligame.com")
            catalog = fetch_dataset(session, args.dataset)
            if args.list_filters:
                for key, values in catalog.options.items():
                    print(f"{FILTER_LABELS[key]}：{'、'.join(values)}")
                return 0
            selected = select_items(catalog, filters, keyword=args.keyword, all_items=args.all_skills)
            print(f"{DATASET_LABELS[args.dataset]}：匹配 {len(selected)} / {len(catalog.skills)} 张图片：")
            for item in selected:
                print(f"  {item.name}.png")
            if args.preview or not selected:
                return 0
            counts = download_icons(selected, args.output.resolve() / args.dataset, session,
                                    overwrite=args.overwrite, delay=args.delay)
            return 1 if counts["failed"] else 0
    except (requests.RequestException, ValueError, OSError) as error:
        print(f"错误：{error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
