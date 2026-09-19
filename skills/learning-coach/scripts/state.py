#!/usr/bin/env python3
"""Local learning checkpoints. Python 3.9+, standard library, no network."""
import argparse
from contextlib import contextmanager
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile

STAGES = {'orient', 'diagnose', 'explain', 'practice', 'challenge', 'transfer', 'review', 'paused', 'complete'}
LABELS = {'exposed', 'assisted', 'explained', 'transferred', 'retained'}
SUPPORT = {'none': 0, 'hint': 1, 'worked_example': 2, 'answer': 3}
KINDS = {'diagnose', 'explain', 'practice', 'transfer', 'review'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def slug(value):
    require(isinstance(value, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', value), 'Invalid topic ID; use lowercase letters, digits, hyphens (1-64).')
    return value


def stamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'Timestamps must include timezone.')
    return parsed


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate(data):
    require(isinstance(data, dict), 'Checkpoint must be an object.')
    required = {'schema_version', 'topic_id', 'title', 'goal', 'sources', 'preferences', 'stage', 'concepts', 'attempts', 'pending_task', 'next_action', 'review_on'}
    require(required <= data.keys(), 'Missing fields: ' + ', '.join(sorted(required - data.keys())))
    require(data['schema_version'] == 1, 'Unsupported schema_version.')
    slug(data['topic_id'])
    for field in ('title', 'goal', 'next_action'):
        require(nonempty(data[field]), field + ' must be nonempty text.')
    require(data['stage'] in STAGES, 'Invalid stage.')
    require(isinstance(data['preferences'], dict), 'preferences must be an object.')
    require(isinstance(data['sources'], list) and all(isinstance(x, str) for x in data['sources']), 'sources must be a list of strings.')
    if data['review_on'] is not None:
        require(isinstance(data['review_on'], str), 'review_on must be a date or null.')
        date.fromisoformat(data['review_on'])
    require(isinstance(data['concepts'], list) and isinstance(data['attempts'], list), 'concepts and attempts must be lists.')
    concepts = {}
    for c in data['concepts']:
        require(isinstance(c, dict) and {'id', 'name', 'label', 'evidence_ids', 'gap'} <= c.keys(), 'Incomplete concept.')
        require(nonempty(c['id']) and c['id'] not in concepts, 'Duplicate or empty concept ID.')
        require(nonempty(c['name']) and isinstance(c['gap'], str), 'Invalid concept name/gap.')
        require(c['label'] in LABELS and isinstance(c['evidence_ids'], list), 'Invalid concept label/evidence_ids.')
        concepts[c['id']] = c
    attempts, help_seen = {}, {}
    for a in data['attempts']:
        fields = {'id', 'concept_id', 'task_id', 'prompt', 'kind', 'answer', 'support', 'outcome', 'feedback', 'at'}
        require(isinstance(a, dict) and fields <= a.keys(), 'Incomplete attempt.')
        require(all(nonempty(a[k]) for k in ('id', 'task_id', 'prompt', 'answer', 'feedback')), 'Attempt text must be nonempty.')
        require(a['id'] not in attempts, 'Duplicate attempt ID.')
        require(a['concept_id'] in concepts, 'Attempt references missing concept.')
        require(a['kind'] in KINDS and a['support'] in SUPPORT and a['outcome'] in {'pass', 'partial', 'fail'}, 'Invalid attempt kind/support/outcome.')
        stamp(a['at'])
        level = SUPPORT[a['support']]
        require(level >= help_seen.get(a['task_id'], 0), 'Cannot downgrade assistance for the same task.')
        help_seen[a['task_id']] = level
        attempts[a['id']] = a
    pending = data['pending_task']
    if pending is not None:
        require(isinstance(pending, dict) and {'task_id', 'concept_id', 'prompt', 'kind', 'support'} <= pending.keys(), 'Incomplete pending_task.')
        require(nonempty(pending['task_id']) and nonempty(pending['prompt']), 'Invalid pending task text.')
        require(pending['concept_id'] in concepts and pending['kind'] in KINDS and pending['support'] in SUPPORT, 'Invalid pending task concept/kind/support.')
        require(SUPPORT[pending['support']] >= help_seen.get(pending['task_id'], 0), 'Pending task loses prior assistance.')
    for c in concepts.values():
        refs = c['evidence_ids']
        require(all(isinstance(i, str) and i in attempts and attempts[i]['concept_id'] == c['id'] for i in refs), 'Evidence must reference attempts for this concept.')
        if c['label'] in {'explained', 'transferred', 'retained'}:
            kind = {'explained': 'explain', 'transferred': 'transfer', 'retained': 'review'}[c['label']]
            evidence = [attempts[i] for i in refs if attempts[i]['kind'] == kind and attempts[i]['support'] == 'none' and attempts[i]['outcome'] == 'pass']
            require(bool(evidence), 'Independent evidence required for ' + c['label'])
            if c['label'] == 'retained':
                require(any(any(p['concept_id'] == c['id'] and p['support'] == 'none' and p['outcome'] == 'pass' and p['kind'] in {'explain', 'transfer', 'review'} and stamp(p['at']).astimezone(timezone.utc).date() < stamp(e['at']).astimezone(timezone.utc).date() for p in attempts.values()) for e in evidence), 'retained requires successful evidence from an earlier UTC date.')
    return data


def location(root, topic):
    root = Path(root).expanduser().resolve()
    folder = root / slug(topic)
    require(not folder.is_symlink(), 'Topic directory must not be a symlink.')
    return folder


def read(root, topic):
    folder = location(root, topic)
    files = sorted(folder.glob('[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].json'))
    if not files:
        raise FileNotFoundError('No learning record for ' + topic)
    path = files[-1]
    require(not path.is_symlink(), 'Checkpoint must not be a symlink.')
    data = validate(json.loads(path.read_text(encoding='utf-8')))
    require(data['topic_id'] == topic and data.get('revision') == int(path.stem), 'Checkpoint identity/revision mismatch.')
    return data


@contextmanager
def lock(folder):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / '.write.lock'
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('Record is locked. Wait for the other writer; inspect a stale lock before manually removing it.')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(str(os.getpid()))
        yield
    finally:
        path.unlink()


def checkpoint(root, data, expected):
    validate(data)
    folder = location(root, data['topic_id'])
    with lock(folder):
        try:
            old = read(root, data['topic_id'])
        except FileNotFoundError:
            old = None
        revision = old['revision'] if old else 0
        require(expected == revision, 'Revision conflict: expected %s, actual %s; re-read before saving.' % (expected, revision))
        require(revision < 99999999, 'Revision limit reached.')
        if old:
            require(data['attempts'][:len(old['attempts'])] == old['attempts'], 'Historical attempts are immutable; append a correction attempt.')
            require({c['id'] for c in old['concepts']} <= {c['id'] for c in data['concepts']}, 'Do not remove existing concept IDs.')
            pending = old['pending_task']
            if pending:
                candidates = data['attempts'][len(old['attempts']):] + ([data['pending_task']] if data['pending_task'] else [])
                for a in candidates:
                    if a['task_id'] == pending['task_id']:
                        require(SUPPORT[a['support']] >= SUPPORT[pending['support']], 'Cannot forget assistance from the saved pending task.')
        result = dict(data, revision=revision + 1, updated_at=datetime.now(timezone.utc).isoformat())
        target = folder / ('%08d.json' % result['revision'])
        require(not target.exists(), 'Checkpoint already exists.')
        fd, tmp = tempfile.mkstemp(prefix='.checkpoint-', dir=folder)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
                f.write('\n')
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return result


def initial(topic, title, goal):
    return dict(schema_version=1, topic_id=slug(topic), title=title, goal=goal, sources=[], preferences={}, stage='orient', concepts=[], attempts=[], pending_task=None, next_action='诊断已有理解，或按零基础要求先给范例。', review_on=None)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', default='.learning-coach', help='Record root, relative to working directory by default.')
    sub = p.add_subparsers(dest='command', required=True)
    i = sub.add_parser('init')
    i.add_argument('--topic', required=True)
    i.add_argument('--title', required=True)
    i.add_argument('--goal', required=True)
    r = sub.add_parser('read')
    r.add_argument('--topic', required=True)
    sub.add_parser('list')
    s = sub.add_parser('save')
    s.add_argument('--input', required=True, help='JSON file or - for stdin; contains the full checkpoint.')
    s.add_argument('--expected-revision', required=True, type=int)
    args = p.parse_args()
    try:
        if args.command == 'init':
            result = checkpoint(args.root, initial(args.topic, args.title, args.goal), 0)
        elif args.command == 'read':
            result = read(args.root, args.topic)
        elif args.command == 'save':
            raw = sys.stdin.read() if args.input == '-' else Path(args.input).read_text(encoding='utf-8')
            result = checkpoint(args.root, json.loads(raw), args.expected_revision)
        else:
            result = []
            for folder in sorted(Path(args.root).expanduser().glob('*')):
                if folder.is_dir() and not folder.is_symlink():
                    try:
                        d = read(args.root, folder.name)
                        result.append({k: d[k] for k in ('topic_id', 'title', 'revision', 'stage', 'next_action', 'review_on')})
                    except (ValueError, OSError, TypeError, KeyError) as e:
                        result.append({'topic_id': folder.name, 'error': str(e)})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as e:
        print('ERROR: ' + str(e), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
