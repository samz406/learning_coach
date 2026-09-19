#!/usr/bin/env python3
"""Install the same portable skill into Claude Code, Codex, or a custom skills directory."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1] / 'skills' / 'learning-coach'


def destinations(platform, scope, project, home=None, skills_dir=None):
    if skills_dir is not None:
        return [Path(skills_dir).expanduser().resolve() / 'learning-coach']
    base = (Path.home() if home is None else Path(home)) if scope == 'user' else Path(project).expanduser().resolve()
    if scope == 'project' and not base.is_dir():
        raise ValueError('Project directory does not exist: ' + str(base))
    mapping = {'claude': '.claude', 'codex': '.agents'}
    platforms = ('claude', 'codex') if platform == 'all' else (platform,)
    return [base / mapping[name] / 'skills' / 'learning-coach' for name in platforms]


def install(targets, replace=False):
    if not (SOURCE / 'SKILL.md').is_file():
        raise ValueError('Source skill is missing.')
    # Preflight every destination before changing any existing installation.
    for target in targets:
        if target.is_symlink():
            raise ValueError('Refusing to replace symlink: ' + str(target))
        if target.resolve() == SOURCE or SOURCE in target.resolve().parents or target.resolve() in SOURCE.parents:
            raise ValueError('Source and destination must not overlap.')
        if target.exists() and (not target.is_dir() or not replace):
            raise ValueError('Destination exists; use --replace to back up and update: ' + str(target))
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.learning-coach-install-', dir=target.parent))
        backup = None
        try:
            shutil.copytree(SOURCE, stage / 'skill', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            if target.exists():
                backup_root = target.parent.parent / 'learning-coach-backups'
                backup_root.mkdir(exist_ok=True)
                tag = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                backup = backup_root / tag
                target.rename(backup)
            try:
                (stage / 'skill').rename(target)
            except OSError:
                if backup is not None:
                    backup.rename(target)
                raise
            print('Installed: ' + str(target))
            if backup is not None:
                print('Previous version: ' + str(backup))
        finally:
            shutil.rmtree(stage)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--platform', choices=('claude', 'codex', 'all'))
    group.add_argument('--skills-dir', help='Custom host discovery directory; appends learning-coach.')
    p.add_argument('--scope', choices=('user', 'project'), default='user')
    p.add_argument('--project-dir', default='.', help='Existing project directory when --scope project.')
    p.add_argument('--replace', action='store_true', help='Back up an existing directory before updating.')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    try:
        targets = destinations(args.platform, args.scope, args.project_dir, skills_dir=args.skills_dir)
        if args.dry_run:
            for target in targets:
                print('Would install: ' + str(target))
        else:
            install(targets, args.replace)
        return 0
    except (OSError, ValueError) as e:
        print('ERROR: ' + str(e), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
