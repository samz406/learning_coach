import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


state = module('state', ROOT / 'skills/learning-coach/scripts/state.py')
installer = module('installer', ROOT / 'scripts/install.py')


def concept(label='exposed', evidence=None):
    return dict(id='c1', name='必要指导', label=label, evidence_ids=evidence or [], gap='区分示例与干扰')


def attempt(ident='a1', kind='explain', support='none', at='2026-09-19T10:00:00+00:00', task='t1'):
    return dict(id=ident, concept_id='c1', task_id=task, prompt='为什么新手需要示例？', kind=kind, answer='示例能减少寻找操作步骤的负担。', support=support, outcome='pass', feedback='说明了降低搜索成本的机制。', at=at)


class Records(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='coach-state-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = state.initial('load', '认知负荷', '独立解释必要指导')

    def test_initialize_read_resume_and_topic_isolation(self):
        saved = state.checkpoint(self.root, self.data, 0)
        draft = copy.deepcopy(saved)
        draft['concepts'] = [concept()]
        draft['pending_task'] = dict(task_id='t1', concept_id='c1', prompt='你怎么判断？', kind='explain', support='hint')
        draft['next_action'] = '等待 t1 的回答，保留已给的提示。'
        state.checkpoint(self.root, draft, 1)
        read = subprocess.run([sys.executable, str(ROOT / 'skills/learning-coach/scripts/state.py'), '--root', str(self.root), 'read', '--topic', 'load'], capture_output=True, text=True, check=True)
        resumed = json.loads(read.stdout)
        self.assertEqual(resumed['pending_task']['support'], 'hint')
        self.assertEqual(resumed['next_action'], draft['next_action'])
        state.checkpoint(self.root, state.initial('cache', '缓存', '解释缓存'), 0)
        self.assertEqual(state.read(self.root, 'cache')['attempts'], [])
        self.assertEqual(state.read(self.root, 'load')['revision'], 2)

    def test_stale_write_and_duplicate_init_do_not_overwrite(self):
        state.checkpoint(self.root, self.data, 0)
        for expected in (0, 99):
            with self.assertRaisesRegex(ValueError, 'Revision conflict'):
                state.checkpoint(self.root, self.data, expected)
        self.assertEqual(state.read(self.root, 'load')['revision'], 1)

    def test_history_is_immutable(self):
        self.data['concepts'] = [concept('explained', ['a1'])]
        self.data['attempts'] = [attempt()]
        saved = copy.deepcopy(state.checkpoint(self.root, self.data, 0))
        saved['attempts'][0]['answer'] = 'modified'
        with self.assertRaisesRegex(ValueError, 'immutable'):
            state.checkpoint(self.root, saved, 1)
        self.assertEqual(state.read(self.root, 'load')['attempts'][0]['answer'], self.data['attempts'][0]['answer'])

    def test_mastery_needs_independent_matching_evidence(self):
        self.data['concepts'] = [concept('transferred', ['a1'])]
        self.data['attempts'] = [attempt(kind='transfer', support='answer')]
        with self.assertRaisesRegex(ValueError, 'Independent evidence'):
            state.validate(self.data)
        self.data['attempts'][0]['support'] = 'none'
        state.validate(self.data)
        self.data['concepts'][0]['evidence_ids'] = ['missing']
        with self.assertRaisesRegex(ValueError, 'Evidence must'):
            state.validate(self.data)

    def test_retention_needs_prior_success_on_earlier_date(self):
        self.data['concepts'] = [concept('retained', ['a2'])]
        self.data['attempts'] = [attempt(), attempt('a2', kind='review', task='t2')]
        with self.assertRaisesRegex(ValueError, 'earlier UTC date'):
            state.validate(self.data)
        self.data['attempts'][1]['at'] = '2026-09-22T10:00:00+00:00'
        state.validate(self.data)

    def test_pending_help_survives_session_boundary(self):
        self.data['concepts'] = [concept()]
        self.data['pending_task'] = dict(task_id='t1', concept_id='c1', prompt='为什么？', kind='explain', support='answer')
        saved = state.checkpoint(self.root, self.data, 0)
        saved['pending_task'] = None
        saved['attempts'] = [attempt(support='none')]
        with self.assertRaisesRegex(ValueError, 'Cannot forget assistance'):
            state.checkpoint(self.root, saved, 1)
        saved['attempts'][0]['support'] = 'answer'
        state.checkpoint(self.root, saved, 1)

    def test_same_task_cannot_reset_assistance(self):
        self.data['concepts'] = [concept()]
        self.data['attempts'] = [attempt(support='hint'), attempt('a2')]
        with self.assertRaisesRegex(ValueError, 'downgrade assistance'):
            state.validate(self.data)

    def test_invalid_state_and_path_traversal_do_not_write(self):
        for key, value in [('stage', 'bogus'), ('review_on', '2026-99-99'), ('schema_version', 99), ('topic_id', '../escape')]:
            d = copy.deepcopy(self.data)
            d[key] = value
            with self.assertRaises(ValueError):
                state.checkpoint(self.root, d, 0)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_locked_or_corrupt_record_is_not_overwritten(self):
        state.checkpoint(self.root, self.data, 0)
        folder = self.root / 'load'
        lock = folder / '.write.lock'
        lock.write_text('other writer')
        with self.assertRaisesRegex(ValueError, 'locked'):
            state.checkpoint(self.root, self.data, 1)
        self.assertEqual(lock.read_text(), 'other writer')
        lock.unlink()
        (folder / '00000002.json').write_text('{broken', encoding='utf-8')
        with self.assertRaises(ValueError):
            state.checkpoint(self.root, self.data, 1)
        self.assertEqual((folder / '00000002.json').read_text(), '{broken')

    def test_cli_input_and_errors(self):
        cmd = [sys.executable, str(ROOT / 'skills/learning-coach/scripts/state.py'), '--root', str(self.root), 'save', '--input', '-', '--expected-revision', '0']
        good = subprocess.run(cmd, input=json.dumps(self.data), text=True, capture_output=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        bad = subprocess.run(cmd, input='not json', text=True, capture_output=True)
        self.assertNotEqual(bad.returncode, 0)
        self.assertNotIn('Traceback', bad.stderr)


class Installation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='coach install 空格 ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_project_and_user_platform_paths(self):
        for scope in ('user', 'project'):
            targets = installer.destinations('all', scope, self.root, home=self.root)
            self.assertEqual(targets, [self.root / '.claude/skills/learning-coach', self.root / '.agents/skills/learning-coach'])

    def test_install_from_readme_in_clean_project_and_dry_run(self):
        cmd = [sys.executable, str(ROOT / 'scripts/install.py'), '--platform', 'all', '--scope', 'project', '--project-dir', str(self.root)]
        subprocess.run(cmd + ['--dry-run'], capture_output=True, check=True)
        self.assertEqual(list(self.root.iterdir()), [])
        subprocess.run(cmd, capture_output=True, check=True)
        for target in installer.destinations('all', 'project', self.root):
            for relative in ('SKILL.md', 'references/teaching.md', 'references/state-protocol.md', 'scripts/state.py', 'assets/learning-record.md', 'agents/openai.yaml'):
                self.assertEqual((target / relative).read_bytes(), (installer.SOURCE / relative).read_bytes())
            result = subprocess.run([sys.executable, str(target / 'scripts/state.py'), '--root', str(self.root / 'records'), 'list'], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout), [])

    def test_repeat_install_protection_backup_and_state_preservation(self):
        target = self.root / 'skills/learning-coach'
        installer.install([target])
        (target / 'custom.txt').write_text('user customization')
        records = self.root / 'records'
        state.checkpoint(records, state.initial('load', '负荷', '解释负荷'), 0)
        with self.assertRaisesRegex(ValueError, 'Destination exists'):
            installer.install([target])
        installer.install([target], replace=True)
        backups = list((self.root / 'learning-coach-backups').glob('*/custom.txt'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), 'user customization')
        self.assertFalse((target / 'custom.txt').exists())
        self.assertEqual(state.read(records, 'load')['revision'], 1)

    def test_all_preflight_preserves_first_target_on_second_conflict(self):
        targets = installer.destinations('all', 'project', self.root)
        targets[1].mkdir(parents=True)
        with self.assertRaises(ValueError):
            installer.install(targets)
        self.assertFalse(targets[0].exists())

    def test_custom_destination_and_source_overlap(self):
        targets = installer.destinations(None, 'user', '.', skills_dir=self.root / 'custom')
        self.assertEqual(targets, [self.root / 'custom/learning-coach'])
        installer.install(targets)
        with self.assertRaisesRegex(ValueError, 'overlap'):
            installer.install([installer.SOURCE], replace=True)


if __name__ == '__main__':
    unittest.main()
