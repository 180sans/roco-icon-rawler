from io import BytesIO
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crawler import (Catalog, Icon, Pet, Selection, Skill, download_icons, filename_for,
                     original_image_url, output_paths, parse_catalog, parse_pet_catalog,
                     select_items, select_skills, valid_png)


def sample(name="星火", season="S4", element="火", category="状态", tags=("异常",)):
    return Skill(name, "https://example.com/icon.png", season, element, category, tags, "无")


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        return FakeResponse(self.content)


class CrawlerTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(
            [sample(), sample("暖阳", category="物攻", tags=("强化",)),
             sample("老技能", season="S1"), sample("水技能", element="水", tags=("天气",))],
            {"season": ["S1", "S4"], "element": ["火", "水"],
             "category": ["状态", "物攻"], "tag": ["异常", "强化", "天气"], "recent": ["无"]})

    def test_s4_excludes_other_seasons_and_groups_intersect(self):
        selected = select_skills(self.catalog, Selection(season=["S4"], element=["火"],
                                                        category=["状态"]))
        self.assertEqual([skill.name for skill in selected], ["星火"])
        selected = select_skills(self.catalog, Selection(season=["S1", "S4"], tag=["异常", "天气"]))
        self.assertEqual([skill.name for skill in selected], ["星火", "老技能", "水技能"])

    def test_empty_and_invalid_filters_never_fall_back_to_all(self):
        for selection in (Selection(), Selection(season=["S44"]),
                          Selection(all_skills=True, season=["S4"])):
            with self.assertRaises(ValueError):
                select_skills(self.catalog, selection)
        self.assertEqual(select_skills(self.catalog, Selection(all_skills=True)), self.catalog.skills)
        self.assertEqual(select_skills(self.catalog, Selection(keyword="不存在")), [])

    def test_actual_card_structure_and_original_icon(self):
        html = '''<div class="nrc-skill-catalog-filter-option" data-skill-catalog-season="S4"></div>
        <div class="nrc-skill-catalog-card" data-skill-catalog-season="S4"
          data-skill-catalog-type="火" data-skill-catalog-category="状态"
          data-skill-catalog-tags="异常|应对" data-skill-catalog-recent="无">
          <div class="nrc-skill-catalog-card-name">星火</div>
          <span class="nrc-skill-catalog-card-icon"><img
          src="https://patchwiki.biligame.com/images/nrc/thumb/9/9e/random.png/96px-Skill_103051.png"></span>
        </div>'''
        catalog = parse_catalog(html)
        self.assertEqual(catalog.skills[0].name, "星火")
        self.assertEqual(catalog.skills[0].tags, ("异常", "应对"))
        self.assertEqual(catalog.skills[0].image_url,
                         "https://patchwiki.biligame.com/images/nrc/9/9e/random.png")
        self.assertEqual(catalog.options["element"], ["火"])
        self.assertEqual(original_image_url("https://example.com/original.png"),
                         "https://example.com/original.png")
        with self.assertRaises(ValueError):
            parse_catalog("<html>网站验证</html>")
        with self.assertRaises(ValueError):
            parse_catalog(html.replace('data-skill-catalog-type="火"', ""))

    def test_windows_names_and_collisions(self):
        self.assertEqual(filename_for("星火"), "星火.png")
        self.assertEqual(filename_for("a/b:c?"), "a_b_c_.png")
        self.assertEqual(filename_for("CON"), "_CON.png")
        with self.assertRaises(ValueError):
            output_paths([sample("a/b"), sample("a:b")], Path("output"))

    def test_real_png_conversion_skip_and_corrupt_file_repair(self):
        source = BytesIO()
        Image.new("RGB", (128, 128), (255, 80, 20)).save(source, format="JPEG")
        session = FakeSession(source.getvalue())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            args = {"delay": 0, "log": lambda _: None}
            self.assertEqual(download_icons([sample()], output, session, **args)["saved"], 1)
            path = output / "星火.png"
            self.assertTrue(valid_png(path))
            self.assertTrue(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual(download_icons([sample()], output, session, **args)["skipped"], 1)
            self.assertEqual(len(session.calls), 1)
            path.write_text("incomplete", encoding="utf-8")
            self.assertEqual(download_icons([sample()], output, session, **args)["saved"], 1)
            self.assertTrue(valid_png(path))
            self.assertEqual(list(output.glob("*.part")), [])

    def test_html_response_does_not_become_png(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            counts = download_icons([sample()], output, FakeSession(b"<html>error</html>"),
                                    delay=0, log=lambda _: None)
            self.assertEqual(counts["failed"], 1)
            self.assertEqual(list(output.iterdir()), [])

    def test_skill_type_and_element_icons_are_named_by_filter_option(self):
        html = '''<div class="nrc-skill-catalog-filter-option" data-skill-catalog-category="物攻">
          <img src="https://example.com/atk.png"></div>
        <div class="nrc-skill-catalog-filter-option" data-skill-catalog-category="状态">
          <img src="https://example.com/status.png"></div>
        <div class="nrc-skill-catalog-filter-option" data-skill-catalog-type="火">
          <img src="https://example.com/fire.png"></div>
        <div class="nrc-skill-catalog-card" data-skill-catalog-season="S4"
          data-skill-catalog-type="火" data-skill-catalog-category="状态"
          data-skill-catalog-tags="异常" data-skill-catalog-recent="无">
          <div class="nrc-skill-catalog-card-name">星火</div>
          <span class="nrc-skill-catalog-card-icon"><img src="https://example.com/skill.png"></span>
        </div>'''
        catalog = parse_catalog(html)
        self.assertEqual(catalog.icons["element"], [Icon("火", "https://example.com/fire.png")])
        selected = select_items(Catalog(catalog.icons["skill_type"], {"name": ["物攻", "状态"]}),
                                {"name": ["物攻"]})
        self.assertEqual([icon.name for icon in selected], ["物攻"])
        self.assertEqual(filename_for(selected[0].name), "物攻.png")

    def test_pet_filename_rules_and_filtering(self):
        html = '''<div class="npc-filter-chip" data-group="form" data-value="lord"></div>
        <div class="npc-card" data-number="011" data-form="main|regional" data-season="S4"
          data-type="普通" data-stage="1"><div class="npc-number">011</div>
          <div class="npc-name">鸭吉吉</div><div class="npc-form">急急急鸭</div>
          <div class="npc-art-head"><img src="https://example.com/yaji.png"></div></div>
        <div class="npc-card" data-number="007" data-form="lord" data-season="none"
          data-type="火" data-stage=""><div class="npc-number">007</div>
          <div class="npc-name">烈火战神</div><div class="npc-form">首领形态</div>
          <div class="npc-art-head"><img src="https://example.com/liehuo.png"></div></div>'''
        catalog = parse_pet_catalog(html)
        self.assertEqual([pet.name for pet in catalog.skills], ["011鸭吉吉（急急急鸭）", "007烈火战神"])
        self.assertEqual([pet.name for pet in select_items(catalog, {"form_kind": ["lord"]})], ["007烈火战神"])
        self.assertEqual([pet.name for pet in select_items(catalog, {"number": ["011"]})], ["011鸭吉吉（急急急鸭）"])
        with self.assertRaises(ValueError):
            parse_pet_catalog(html.replace('class="npc-art-head"', 'class="npc-art-normal"'))
        with self.assertRaises(ValueError):
            parse_pet_catalog(html + html)
        no_form = Pet("001", "迪莫", "", "https://example.com/dimo.png", ("none",), ("光",), ("main",), "1")
        self.assertEqual(filename_for(no_form.name), "001迪莫.png")


if __name__ == "__main__":
    unittest.main()
