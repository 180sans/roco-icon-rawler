"""Exercise real Tk widgets without showing windows or performing HTTP requests."""
from pathlib import Path
import sys
import tkinter as tk
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crawler import Catalog, Skill
from gui import App, SCOPE_LABELS


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = App(self.root, Path('.').resolve())

    def tearDown(self):
        self.root.destroy()

    def execute(self, scope='current'):
        result = dict(saved=0, skipped=1, failed=0, category_errors=0, stopped=False, datasets={})
        with patch('gui.threading.Thread') as thread, \
                patch('gui.new_session'), patch('gui.crawl_images', return_value=result) as crawl:
            self.app.start(scope)
            self.assertTrue(self.app.busy)
            self.assertEqual(str(self.app.total_button['state']), 'disabled')
            thread.call_args.kwargs['target']()
            self.app.poll()
            self.assertFalse(self.app.busy)
            self.assertIn('下载结束', self.app.status.get())
            return crawl.call_args.kwargs

    def test_default_total_crawl_is_ready_and_missing_only(self):
        self.assertEqual(self.app.dataset, 'all')
        self.assertTrue(self.app.missing_only.get())
        self.assertEqual(str(self.app.total_button['state']), 'normal')
        args = self.execute()
        self.assertEqual(args['dataset'], 'all')
        self.assertTrue(args['missing_only'])
        self.app.missing_only.set(False)
        args = self.execute('all')
        self.assertFalse(args['missing_only'])

    def test_subclass_uses_same_mode_and_total_ignores_filters(self):
        records = [Skill('测试技能', 'https://example.com/a.png', 'S4', '火', '状态', (), '无')]
        self.app.cache['skill'] = Catalog(records, {'season': ['S4']})
        self.app.dataset_label.set(SCOPE_LABELS['skill'])
        self.app.switch_dataset()
        self.assertTrue(self.app.all_items.get())
        self.app.checks['season']['S4'].set(True)
        self.app.changed()
        args = self.execute()
        self.assertEqual(args['dataset'], 'skill')
        self.assertEqual(args['filters'], {'season': ['S4']})
        self.assertFalse(args['all_items'])
        self.assertTrue(args['missing_only'])
        self.app.missing_only.set(False)
        args = self.execute()
        self.assertFalse(args['missing_only'])
        args = self.execute('all')
        self.assertEqual(args['dataset'], 'all')
        self.assertEqual(args['filters'], {})
        self.assertTrue(args['all_items'])

    def test_keyword_exits_current_category_all(self):
        self.app.cache['skill_type'] = Catalog([], {'name': []})
        self.app.dataset_label.set(SCOPE_LABELS['skill_type'])
        self.app.switch_dataset()
        self.app.keyword.set('物攻')
        self.assertFalse(self.app.all_items.get())


if __name__ == '__main__':
    unittest.main()
