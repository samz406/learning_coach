#!/usr/bin/env python3
"""Check portable metadata, bundled references, Python syntax, and Markdown links."""
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
skill = ROOT / 'skills/learning-coach'
text = (skill / 'SKILL.md').read_text(encoding='utf-8')
assert text.startswith('---\n'), 'Missing YAML frontmatter'
front = text.split('---', 2)[1]
fields = dict(line.split(':', 1) for line in front.strip().splitlines())
assert set(fields) == {'name', 'description'}, 'Use portable name/description only'
assert fields['name'].strip() == skill.name
assert fields['description'].strip()
assert len(text.splitlines()) < 500
for path in ROOT.rglob('*.md'):
    if '.git' in path.parts or '.learning-coach' in path.parts:
        continue
    for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
        if '://' in target or target.startswith('#'):
            continue
        assert (path.parent / target.split('#')[0]).exists(), f'Broken link in {path}: {target}'
for path in ROOT.rglob('*.py'):
    if '.git' not in path.parts:
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
assert 'TODO' not in text and '[TODO' not in (skill / 'agents/openai.yaml').read_text(encoding='utf-8')
print('PASS: metadata, bundled resources, Markdown links, Python syntax')
