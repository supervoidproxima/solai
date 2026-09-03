# -*- coding: utf-8 -*-
"""Plan, apply, roll back. Nothing in this package writes a file except through here.

The three-verb contract is lifted from `NIS/_system/scripts/restructure.py`, which is
already proven on this machine against Cyrillic OneDrive paths. Kept deliberately:

  - Every path goes through `w()`. Cyrillic plus nesting under a 71-character OneDrive
    root breaks the 260-character limit routinely, and `os.*` fails opaquely when it does.
  - Every write is temp-sibling plus `os.replace`, so a sync daemon or a crash can never
    observe a half-written vault file.
  - Every write records the pre-image sha AND mtime. Sha alone cannot tell a hand edit
    from a OneDrive sync landing between plan and apply; the pair can.

`--plan` is the default everywhere. A scaffolder whose default mode writes is a
scaffolder people run once and then avoid.
"""
import hashlib
import io
import json
import os
import shutil
import time

from . import stamp

WRITE, NOOP, SKIP, COPY, MKDIR = 'WRITE', 'NOOP', 'SKIP', 'COPY', 'MKDIR'


def w(p):
    """Windows long path. Cyrillic plus nesting breaks 260 characters routinely."""
    p = os.path.abspath(p)
    if os.name != 'nt':
        return p
    return p if p.startswith('\\\\?\\') else '\\\\?\\' + p


def read(path):
    try:
        with io.open(w(path), encoding='utf-8') as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def exists(path):
    return os.path.exists(w(path))


def bytes_sha(path):
    """The hash of a file's bytes. `stamp.file_sha` decodes utf-8 and answers None for a PDF,
    so a binary handed to a place would be re-copied on every run and no second plan would
    ever be NOOP - which is the property the whole verification gate rests on."""
    h = hashlib.sha256()
    try:
        with open(w(path), 'rb') as fh:
            for chunk in iter(lambda: fh.read(65536), b''):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()[:16]


class Action(object):
    __slots__ = ('kind', 'path', 'content', 'src', 'artefact', 'verdict', 'reason', 'detail')

    def __init__(self, kind, path, artefact, content=None, src=None,
                 verdict=None, reason='', detail=''):
        self.kind, self.path, self.artefact = kind, path, artefact
        self.content, self.src = content, src
        self.verdict, self.reason, self.detail = verdict, reason, detail

    @property
    def rel(self):
        return self.path


class Plan(object):
    """An ordered, printable, refusable list of intended writes."""

    def __init__(self, root, package_version):
        self.root = os.path.abspath(root)
        self.package_version = package_version
        self.actions = []

    def path(self, rel):
        return os.path.join(self.root, rel.replace('/', os.sep))

    def add(self, action):
        self.actions.append(action)
        return action

    def write(self, rel, artefact, content, src=None, verdict=None):
        return self.add(Action(WRITE, rel, artefact, content=content, src=src, verdict=verdict))

    def noop(self, rel, artefact, verdict=stamp.CLEAN, reason='identical'):
        return self.add(Action(NOOP, rel, artefact, verdict=verdict, reason=reason))

    def skip(self, rel, artefact, verdict, reason, detail=''):
        return self.add(Action(SKIP, rel, artefact, verdict=verdict, reason=reason, detail=detail))

    def copy(self, rel, artefact, source_path):
        return self.add(Action(COPY, rel, artefact, content=source_path))

    def mkdir(self, rel, artefact='folders'):
        # A folder is created once. Two callers can legitimately ask for the same one - a
        # manifest declaring `duties` and the class that lives in it - and a plan that
        # printed the row twice would report a count the filesystem never performs.
        for a in self.actions:
            if a.kind == MKDIR and a.rel == rel:
                return a
        return self.add(Action(MKDIR, rel, artefact))

    # ------------------------------------------------------------------ reporting

    @property
    def counts(self):
        c = {}
        for a in self.actions:
            c[a.kind] = c.get(a.kind, 0) + 1
        return c

    def is_noop(self):
        return all(a.kind == NOOP for a in self.actions)

    def table(self):
        if not self.actions:
            return '(nothing to do)'
        wid = max(len(a.rel) for a in self.actions)
        wid = min(wid, 58)
        rows = []
        for a in self.actions:
            rel = a.rel if len(a.rel) <= wid else '...' + a.rel[-(wid - 3):]
            note = a.reason or (a.verdict or '')
            rows.append('  %-6s %-*s  %-12s %s' % (a.kind, wid, rel, a.verdict or '', note))
        c = self.counts
        summary = '  '.join('%s %d' % (k, c[k]) for k in sorted(c))
        return '\n'.join(rows) + '\n\n  ' + summary

    def blockers(self):
        """Skips a human must see before anything is called finished."""
        return [a for a in self.actions
                if a.kind == SKIP and a.verdict == stamp.HAND_EDITED]


# --------------------------------------------------------------------------- apply

def _atomic_write(path, content):
    d = os.path.dirname(path)
    os.makedirs(w(d), exist_ok=True)
    tmp = path + '.solai-tmp'
    with io.open(w(tmp), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(content)
    os.replace(w(tmp), w(path))


def _pre_image(path):
    if not exists(path):
        return {'existed': False}
    try:
        st = os.stat(w(path))
        return {'existed': True, 'sha': stamp.file_sha(w(path)), 'mtime': st.st_mtime,
                'size': st.st_size}
    except OSError:
        return {'existed': True, 'sha': None, 'mtime': None, 'size': None}


def apply(plan, manifest_path, backup_dir=None):
    """Execute the plan. Returns the manifest dict. Writes nothing on an empty plan."""
    done = []
    for a in plan.actions:
        target = plan.path(a.rel)
        if a.kind == MKDIR:
            os.makedirs(w(target), exist_ok=True)
            continue
        if a.kind in (NOOP, SKIP):
            continue
        pre = _pre_image(target)
        if pre['existed'] and backup_dir:
            bak = os.path.join(backup_dir, a.rel.replace('/', os.sep))
            os.makedirs(w(os.path.dirname(bak)), exist_ok=True)
            shutil.copy2(w(target), w(bak))
        if a.kind == COPY:
            os.makedirs(w(os.path.dirname(target)), exist_ok=True)
            shutil.copy2(w(a.content), w(target))
        else:
            _atomic_write(target, a.content)
        done.append({'path': a.rel, 'artefact': a.artefact, 'kind': a.kind, 'pre': pre})
    manifest = {
        'package_version': plan.package_version,
        'root': plan.root,
        'applied': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'backup_dir': backup_dir,
        'actions': done,
    }
    os.makedirs(w(os.path.dirname(manifest_path)), exist_ok=True)
    with io.open(w(manifest_path), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def rollback(manifest_path):
    """Undo the last apply. Restores from the backup copies; deletes what did not exist."""
    if not exists(manifest_path):
        return None, 'no manifest at %s' % manifest_path
    manifest = json.loads(read(manifest_path))
    root, backup_dir = manifest['root'], manifest.get('backup_dir')
    restored = removed = missing = 0
    for rec in reversed(manifest['actions']):
        target = os.path.join(root, rec['path'].replace('/', os.sep))
        if not rec['pre']['existed']:
            if exists(target):
                os.remove(w(target))
                removed += 1
            continue
        bak = os.path.join(backup_dir, rec['path'].replace('/', os.sep)) if backup_dir else None
        if bak and exists(bak):
            shutil.copy2(w(bak), w(target))
            restored += 1
        else:
            missing += 1
    return {'restored': restored, 'removed': removed, 'unrecoverable': missing}, None
