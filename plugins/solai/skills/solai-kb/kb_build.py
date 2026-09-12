#!/usr/bin/env python3
"""Build a knowledge base out of an authoring vault.

    py kb_build.py <kb-folder> [--out DIR] [--dry-run]

Three things, three homes, and the build keeps them apart. The vault holds the
client's work and never receives a file from here. Solai's package holds the
engine and never holds any client's rules. A knowledge base is the third thing:
one folder with a kb.toml in it, naming the vault it reads and holding what it
built.

Phase 0 of the roadmap. Turns a vault into a `kb/` that a program can read without
ever touching the vault again: one record per citable unit, one full-text index,
one manifest that says what went in and what was refused and why.

Provenance is a corpus hash, not a commit. The vaults are deliberately not in git
(1.2 GB of attachments is not what git is for), so the build hashes the selected
file set instead: path, size and content digest of every file that made it in.
Same corpus hash must mean the same bytes out.

Four things make the build refuse rather than publish something doubtful:

  placeholders   a selected file is an OneDrive cloud placeholder. Reading one
                 either blocks or silently yields nothing, and a file that is not
                 really here must never become an answer.
  dangling       a record claims an anchor that is not in the text it came from.
  drift          the same corpus AND the same builder produced different records
                 than last time. That is non-determinism, and it makes every
                 citation unstable. A changed builder is expected to differ.
  shrink         the record count fell by more than the allowed margin. A broken
                 selection rule looks exactly like a successful build.

Standard library only. Python 3.11+ for tomllib.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import sys
import time
import tomllib
from pathlib import Path, PurePosixPath

# The shared wikilink pattern, from `runtime/`. Imported by path rather than by package:
# these scripts live in the package and are never copied into a vault, so unlike the
# scripts a vault runs there is no copy of it beside them.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime'))
import _wikilink                                                    # noqa: E402

SCHEMA = 1


def builder_hash() -> str:
    """This file's own digest. Extraction logic is an input to the output, so a
    change here has to be visible next to the corpus it was applied to."""
    try:
        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
    except OSError:
        return 'unknown'

# Windows marks a file that lives in the cloud rather than on the disk. Reading one
# makes the provider fetch it, which can block for a long time or fail outright, and
# on a machine where the vault is not pinned the whole corpus can look present and
# be empty. See the OneDrive stop in the installer: same fault, later consequence.
FILE_ATTRIBUTE_OFFLINE = 0x00001000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x00040000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000
PLACEHOLDER_MASK = (FILE_ATTRIBUTE_OFFLINE
                    | FILE_ATTRIBUTE_RECALL_ON_OPEN
                    | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS)

ANCHOR_RE = re.compile(r'\^([0-9a-f]{6})\s*$')
INLINE_ANCHOR_RE = re.compile(r'\s*\^[0-9a-f]{6}\b')
FOOTNOTE_REF_RE = re.compile(r'\[\^[0-9]+\]')
FOOTNOTE_DEF_RE = re.compile(r'(?m)^\[\^[0-9]+\]:.*$')
EMBED_RE = re.compile(r'!\[\[[^\]]*\]\]')
COMMENT_RE = re.compile(r'(?s)<!--.*?-->')


def serve_text(text: str) -> str:
    """What the model will actually read.

    The vault's own notation is noise once a fragment is out of the vault: a
    reader with no Obsidian cannot follow a wikilink, an anchor is an address and
    not a word, and a footnote marker points at a list that was left behind. Each
    of them costs tokens in a language that already costs about twice per
    character what English does. The link targets survive as fields on the record.
    """
    t = COMMENT_RE.sub('', text)
    t = EMBED_RE.sub('', t)
    t = FOOTNOTE_DEF_RE.sub('', t)
    t = FOOTNOTE_REF_RE.sub('', t)
    t = INLINE_ANCHOR_RE.sub('', t)
    t = _wikilink.LINK.sub(lambda m: (m.group(2) or m.group(1)).strip(), t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()


def est_tokens(text: str) -> int:
    """Rough. Cyrillic runs about 2.5 characters to the token, Latin about 4.
    Rough is enough to budget a prompt; it is not enough to bill against."""
    cyr = sum(1 for ch in text if '\u0400' <= ch <= '\u04ff')
    return round(cyr / 2.5 + (len(text) - cyr) / 4.0)
HEADING_RE = re.compile(r'^(#{1,6})\s+(.*?)\s*$')
CLAUSE_NO_RE = re.compile(r'^([0-9]+(?:\.[0-9]+)*)\.?\s*')


# --------------------------------------------------------------------------- report
class Report:
    """Console output. Verbose is free; the manifest is what has to stay terse."""

    def __init__(self) -> None:
        self.failed = False

    def stage(self, text: str) -> None:
        print('\n[%s]' % text)

    def say(self, verdict: str, text: str) -> None:
        print('      %-11s %s' % (verdict, text))

    def fail(self, text: str) -> None:
        self.failed = True
        self.say('failed', text)


# --------------------------------------------------------------------------- frontmatter
def split_frontmatter(text: str) -> tuple[dict, str, int]:
    """Return (frontmatter, body, body_start_line).

    A deliberately small YAML reader: scalars, inline empty lists, and block lists
    of scalars. That is the whole shape the vault's frontmatter takes, and a real
    YAML parser is a dependency this build does not need.
    """
    if not text.startswith('---'):
        return {}, text, 0
    end = text.find('\n---', 3)
    if end < 0:
        return {}, text, 0
    head = text[3:end]
    body_start = text.find('\n', end + 1) + 1
    fm: dict = {}
    key = None
    for raw in head.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if line.startswith('  - ') or line.startswith('- '):
            if key is not None:
                fm.setdefault(key, [])
                if isinstance(fm[key], list):
                    fm[key].append(_scalar(line.split('- ', 1)[1]))
            continue
        if ':' not in line:
            continue
        k, _, v = line.partition(':')
        key = k.strip()
        v = v.strip()
        if v == '':
            fm[key] = []                      # a block list may follow, or nothing
        elif v in ('[]', '[ ]'):
            fm[key] = []
            key = None
        elif v.startswith('['):
            fm[key] = [_scalar(p) for p in v.strip('[]').split(',') if p.strip()]
            key = None
        else:
            fm[key] = _scalar(v)
            key = None
    return fm, text[body_start:], text[:body_start].count('\n')


def _scalar(v: str):
    v = v.strip().strip('"').strip("'")
    return v


def wikitargets(value) -> list[str]:
    """`"[[PRC-037]]"` and `"[[R2R|R2R]]"` both become their target."""
    return _wikilink.targets(value)


# --------------------------------------------------------------------------- selection
class Selector:
    def __init__(self, cfg: dict) -> None:
        inc = cfg.get('include', {})
        exc = cfg.get('exclude', {})
        self.inc_paths = list(inc.get('paths', []))
        self.exc_paths = list(exc.get('paths', []))
        self.exc_status = {s.lower() for s in exc.get('status', [])}
        self.inc_status = {s.lower() for s in inc.get('status', [])}
        self.refusals: list[tuple[str, str]] = []

    @staticmethod
    def _match(rel: str, pat: str) -> bool:
        # full_match, not fnmatch: fnmatch's `*` crosses a separator, so every
        # pattern would silently behave like `**` and the selection would be wider
        # than the rules file appears to say.
        return PurePosixPath(rel).full_match(pat)

    def path_ok(self, rel: str) -> tuple[bool, str]:
        for pat in self.exc_paths:                      # exclude always wins
            if self._match(rel, pat):
                return False, 'exclude.paths ' + pat
        for pat in self.inc_paths:
            if self._match(rel, pat):
                return True, ''
        return False, 'not in include.paths'

    def status_ok(self, rel: str, fm: dict) -> tuple[bool, str]:
        st = str(fm.get('status', '') or '').lower()
        if st and st in self.exc_status:
            return False, 'exclude.status ' + st
        if self.inc_status and st and st not in self.inc_status:
            return False, 'status not in include.status (%s)' % st
        return True, ''

    def refuse(self, rel: str, why: str) -> None:
        self.refusals.append((rel, why))


# --------------------------------------------------------------------------- records
def clause_records(doc_id: str, title: str, rel: str, body: str, cap: int) -> list[dict]:
    """A regulation becomes one record per numbered clause.

    Split at headings, because that is where meaning already ends. A fixed window
    would cut a clause away from the condition that governs it and hand the model
    half a rule. The block anchor, where the vault has minted one, travels with the
    record: that is what makes the citation exact rather than approximate.
    """
    records, cur = [], None
    section = ''
    lines = body.splitlines()

    # Read the document's own shape rather than assuming one. Where two heading
    # levels are used, the shallower names the part and the next one down is the
    # clause. Where only one is used, that one is the clause and there are no
    # parts. Assuming otherwise cost nine regulations their entire text.
    levels = sorted({len(m.group(1)) for m in
                     (HEADING_RE.match(x) for x in lines) if m})
    if not levels:
        return []
    sec_level = levels[0] if len(levels) >= 2 else None
    clause_level = levels[1] if len(levels) >= 2 else levels[0]

    def close(rec):
        if rec is None:
            return
        text = '\n'.join(rec['_lines']).strip()
        if not text:
            return
        rec.pop('_lines')
        served = serve_text(text)
        # Split rather than truncate. A passage that looks whole and has lost the
        # sentence carrying its condition is worse than an obviously partial one.
        atoms = []
        for para in served.split('\n\n'):
            if len(para) <= cap:
                atoms.append(para)
                continue
            # One paragraph over the cap: a clause whose body is a long list.
            # Sentences next, and a sentence that is still too long by force.
            piece = ''
            for sent in re.split(r'(?<=[.;:])\s+', para):
                while len(sent) > cap:
                    atoms.append(sent[:cap])
                    sent = sent[cap:]
                if piece and len(piece) + len(sent) + 1 > cap:
                    atoms.append(piece)
                    piece = sent
                else:
                    piece = (piece + ' ' + sent) if piece else sent
            if piece:
                atoms.append(piece)

        parts, buf = [], ''
        for atom in atoms:
            if buf and len(buf) + len(atom) + 2 > cap:
                parts.append(buf)
                buf = atom
            else:
                buf = (buf + '\n\n' + atom) if buf else atom
        parts.append(buf)
        parts = [x for x in parts if x.strip()] or ['']
        for n, part in enumerate(parts, 1):
            out = dict(rec)
            if len(parts) > 1:
                out['id'] = '%s/%d' % (rec['id'], n)
                out['cite'] = '%s (часть %d из %d)' % (rec['cite'], n, len(parts))
                out['breadcrumb'] = '%s › часть %d из %d' % (rec['breadcrumb'], n, len(parts))
            out['text'] = part[:cap]
            out['part'] = n
            out['parts'] = len(parts)
            out['truncated'] = len(part) > cap
            out['tokens'] = est_tokens(out['text']) + est_tokens(out['breadcrumb'])
            records.append(out)

    for line in lines:
        m = HEADING_RE.match(line)
        if m and sec_level is not None and len(m.group(1)) == sec_level:
            section = ANCHOR_RE.sub('', m.group(2)).strip()
            continue
        if m and len(m.group(1)) >= clause_level:
            close(cur)
            head = m.group(2)
            anchor = None
            a = ANCHOR_RE.search(head)
            if a:
                anchor = a.group(1)
                head = ANCHOR_RE.sub('', head).strip()
            no = CLAUSE_NO_RE.match(head)
            clause = no.group(1) if no else None
            cur = {
                'id': '%s#^%s' % (doc_id, anchor) if anchor
                      else '%s#%s' % (doc_id, clause or head[:40]),
                'kind': 'regulation.clause',
                'parent': doc_id,
                'title': '%s, п. %s' % (title, clause) if clause else '%s, %s' % (title, head),
                'path': rel,
                'anchor': anchor,
                'clause': clause,
                'cite_kind': 'anchor' if anchor else ('clause' if clause else 'heading'),
                'cite': ('%s, п. %s' % (doc_id, clause)) if clause else
                        ('%s, %s' % (doc_id, head[:60])),
                'link': ('[[%s#^%s|%s]]' % (doc_id, anchor, doc_id)) if anchor else None,
                'section': section,
                # The trail back. A clause that says "в этом случае" has lost its
                # referent the moment it is retrieved alone; this is what returns it.
                'breadcrumb': ' \u203a '.join(x for x in (
                    '%s \u00b7 %s' % (doc_id, title[:90]),
                    section,
                    ('\u043f. %s' % clause) if clause else head[:60]) if x),
                '_lines': [],
            }
            continue
        if cur is not None:
            cur['_lines'].append(line)
    close(cur)
    return records


def card_record(doc_id: str, fm: dict, rel: str, body: str, cap: int) -> dict:
    """A card is one record. It is already the size of one idea, which is the whole
    reason the vault mints them."""
    text = serve_text(body)
    title = str(fm.get('title') or fm.get('text') or fm.get('statement')
                or fm.get('question') or fm.get('subject') or doc_id)
    return {
        'id': doc_id,
        'kind': 'card.' + str(fm.get('type', 'note')),
        'parent': None,
        'title': title[:200],
        'path': rel,
        'anchor': None,
        'clause': None,
        'cite_kind': 'card',                 # the id itself is the citation
        'cite': doc_id,
        'link': '[[%s]]' % doc_id,
        'section': '',
        'breadcrumb': '%s \u00b7 %s' % (doc_id, str(fm.get('type', 'card'))),
        'text': text[:cap],
        'truncated': len(text) > cap,
        'tokens': est_tokens(text[:cap]),
    }


def section_records(doc_id: str, title: str, rel: str, body: str, cap: int) -> list[dict]:
    """Everything else: one record per H2. Anchors kept where they exist."""
    recs = clause_records(doc_id, title, rel, body, cap)
    for r in recs:
        r['kind'] = 'document.section'
    return recs


# --------------------------------------------------------------------------- build
def build(vault: Path, cfg: dict, out: Path, rep: Report, dry: bool,
          shrink_pct: float) -> int:
    cap = int(cfg.get('chunk', {}).get('max_chars', 1800))
    gran = cfg.get('granularity', {})
    clause_types = {t.lower() for t in gran.get('clause', ['ird'])}
    card_types = {t.lower() for t in gran.get('card', [])}
    sel = Selector(cfg)

    # ---------------------------------------------------------------- 1. select
    rep.stage('select')
    files: list[tuple[str, Path]] = []
    for path in sorted(vault.rglob('*.md')):
        rel = PurePosixPath(path.relative_to(vault)).as_posix()
        ok, why = sel.path_ok(rel)
        if not ok:
            sel.refuse(rel, why)
            continue
        files.append((rel, path))
    rep.say('ok', '%d files match the paths' % len(files))

    # ---------------------------------------------------------------- 2. placeholders
    rep.stage('materialised')
    placeholders = []
    for rel, path in files:
        try:
            attrs = getattr(path.stat(), 'st_file_attributes', 0)
        except OSError as exc:
            rep.fail('cannot stat %s: %s' % (rel, exc))
            continue
        if attrs & PLACEHOLDER_MASK:
            placeholders.append(rel)
    if placeholders:
        rep.fail('%d selected files are cloud placeholders, not on this disk'
                 % len(placeholders))
        for rel in placeholders[:5]:
            rep.say('', '  ' + rel)
        rep.say('', '  pin the vault folder: right-click, Always keep on this device')
        return 1
    rep.say('ok', 'every selected file is really here')

    # ---------------------------------------------------------------- 3. records
    rep.stage('records')
    records: list[dict] = []
    corpus = hashlib.sha256()
    docs: dict[str, str] = {}
    for rel, path in files:
        raw = path.read_bytes()
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            sel.refuse(rel, 'not utf-8')
            continue
        fm, body, _ = split_frontmatter(text)
        ok, why = sel.status_ok(rel, fm)
        if not ok:
            sel.refuse(rel, why)
            continue

        doc_id = str(fm.get('id') or Path(rel).stem)
        dtype = str(fm.get('type', '')).lower()
        title = str(fm.get('title') or Path(rel).stem)
        corpus.update(rel.encode('utf-8'))
        corpus.update(hashlib.sha256(raw).digest())

        if dtype in card_types:
            new = [card_record(doc_id, fm, rel, body, cap)]
        elif dtype in clause_types:
            new = clause_records(doc_id, title, rel, body, cap)
        else:
            new = section_records(doc_id, title, rel, body, cap)

        facets = {
            'type': dtype or 'unknown',
            'status': str(fm.get('status', '') or ''),
            'kind': str(fm.get('kind', '') or ''),
            'severity': str(fm.get('severity', '') or ''),
            'date': str(fm.get('date', '') or '')[:10],
            'stream': wikitargets(fm.get('stream', [])),
            'entity': wikitargets(fm.get('entity', [])),
            'system': wikitargets(fm.get('system', [])),
            'process': wikitargets(fm.get('process', [])),
        }
        links = sorted({t for k in ('gap', 'pain', 'proposal', 'question', 'hypothesis',
                                    'case', 'request', 'resolution', 'project', 'related')
                        for t in wikitargets(fm.get(k, []))})
        if not new:
            sel.refuse(rel, 'no records: the body has no headings to split on')
        for r in new:
            r['facets'] = facets
            r['links'] = links
            r['doc_type'] = dtype
            records.append(r)
        docs[doc_id] = text

    corpus_hash = corpus.hexdigest()[:16]
    rep.say('ok', '%d records from %d documents' % (len(records), len(docs)))
    rep.say('ok', 'corpus %s' % corpus_hash)
    by_kind: dict[str, int] = {}
    for r in records:
        by_kind[r['kind']] = by_kind.get(r['kind'], 0) + 1
    for k in sorted(by_kind, key=lambda x: -by_kind[x])[:8]:
        rep.say('', '  %-28s %d' % (k, by_kind[k]))
    cites: dict[str, int] = {}
    for r in records:
        cites[r['cite_kind']] = cites.get(r['cite_kind'], 0) + 1
    citable = len(records) - cites.get('heading', 0)
    rep.say('ok', 'every record can be named: %s'
            % ', '.join('%s %d' % (k, cites[k]) for k in sorted(cites)))
    rep.say('ok', '%d of %d can be deep-linked or numbered' % (citable, len(records)))
    cut = sum(1 for r in records if r.get('truncated'))
    if cut:
        rep.say('action', '%d records still exceed the cap and were cut' % cut)
    split = len({r['id'].rsplit('/', 1)[0] for r in records if r.get('parts', 1) > 1})
    if split:
        rep.say('ok', '%d long clauses split into parts rather than truncated' % split)
    toks = [r['tokens'] for r in records]
    toks.sort()
    rep.say('ok', 'record size: median %d tokens, p95 %d, a six-record answer ~%d'
            % (toks[len(toks) // 2], toks[int(len(toks) * 0.95)],
               toks[int(len(toks) * 0.95)] * 6))

    # ---------------------------------------------------------------- 4. dangling
    rep.stage('anchors')
    dangling = [r['id'] for r in records
                if r['anchor'] and ('^' + r['anchor']) not in docs.get(r['parent'] or '', '')]
    if dangling:
        rep.fail('%d records claim an anchor their document does not contain' % len(dangling))
        for d in dangling[:5]:
            rep.say('', '  ' + d)
        return 1
    rep.say('ok', 'every anchor resolves')

    # ---------------------------------------------------------------- 5. refusals
    rep.stage('refused')
    rep.say('ok', '%d files refused' % len(sel.refusals))
    grouped: dict[str, int] = {}
    for _, why in sel.refusals:
        head = why.split(' ')[0] if why.startswith('exclude') else why
        grouped[head] = grouped.get(head, 0) + 1
    for k in sorted(grouped, key=lambda x: -grouped[x]):
        rep.say('', '  %-22s %d' % (k, grouped[k]))

    if dry:
        rep.stage('dry run')
        rep.say('', 'nothing written. Drop --dry-run to build into %s' % out)
        return 0

    # ---------------------------------------------------------------- 6. shrink gate
    prev = None
    manifest_path = out / 'manifest.json'
    if manifest_path.exists():
        try:
            prev = json.loads(manifest_path.read_text('utf-8'))
        except (OSError, ValueError):
            prev = None
    if prev:
        was, now = int(prev.get('records', 0)), len(records)
        if was and now < was * (1 - shrink_pct / 100.0):
            rep.stage('shrink')
            rep.fail('records fell from %d to %d, more than %.0f%%. A selection rule that '
                     'quietly de-published half the corpus reads exactly like a good build. '
                     'Re-run with --allow-shrink if this is intended.' % (was, now, shrink_pct))
            return 1
        if prev.get('corpus') == corpus_hash:
            rep.stage('determinism')
            if prev.get('builder') != builder_hash():
                rep.say('ok', 'same corpus, but the builder changed since %s. '
                              'Records may legitimately differ: %d then, %d now.'
                        % (prev.get('built', 'the last build')[:10],
                           prev.get('records', 0), len(records)))
            elif prev.get('records') != len(records):
                rep.say('failed', 'same corpus and same builder')
                rep.fail('identical input produced a different record count: %d then, %d now'
                         % (prev.get('records'), len(records)))
                return 1
            else:
                rep.say('ok', 'same corpus, same builder, same records')

    # ---------------------------------------------------------------- 7. write
    rep.stage('write')
    if out.exists():
        shutil.rmtree(out)
    (out / 'docs').mkdir(parents=True)

    records.sort(key=lambda r: (r['path'], r['id']))
    lines = []
    for r in records:
        r = dict(r)
        r['corpus'] = corpus_hash
        lines.append(json.dumps(r, ensure_ascii=False, sort_keys=True))
    payload = '\n'.join(lines) + '\n'
    (out / 'records.jsonl').write_text(payload, encoding='utf-8', newline='\n')
    records_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]
    rep.say('ok', 'records.jsonl  %d lines' % len(lines))

    for doc_id, text in sorted(docs.items()):
        safe = re.sub(r'[^0-9A-Za-zА-Яа-яЁё _.\-]', '_', doc_id)[:120]
        (out / 'docs' / (safe + '.md')).write_text(text, encoding='utf-8', newline='\n')
    rep.say('ok', 'docs/          %d documents' % len(docs))

    db_path = out / 'index.sqlite'
    con = sqlite3.connect(db_path)
    try:
        con.execute("CREATE VIRTUAL TABLE fts USING fts5(id UNINDEXED, title, text)")
    except sqlite3.OperationalError:
        rep.fail('this Python has no FTS5. Install a build of sqlite with FTS5 enabled.')
        con.close()
        return 1
    con.execute("""CREATE TABLE facet(
        id TEXT, kind TEXT, doc_type TEXT, status TEXT, gap_kind TEXT, severity TEXT,
        date TEXT, stream TEXT, entity TEXT, system TEXT, process TEXT,
        citable INT, path TEXT, title TEXT)""")
    for r in records:
        f = r['facets']
        con.execute("INSERT INTO fts(id,title,text) VALUES (?,?,?)",
                    (r['id'], r['title'], r['text']))
        con.execute("INSERT INTO facet VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            r['id'], r['kind'], r['doc_type'], f['status'], f['kind'], f['severity'],
            f['date'], ' '.join(f['stream']), ' '.join(f['entity']), ' '.join(f['system']),
            ' '.join(f['process']), 1 if r['cite_kind'] != 'heading' else 0, r['path'], r['title']))
    con.execute("CREATE INDEX facet_id ON facet(id)")
    con.execute("CREATE INDEX facet_type ON facet(doc_type)")
    con.commit()
    con.close()
    rep.say('ok', 'index.sqlite   fts5 + facets')

    manifest = {
        'schema': SCHEMA,
        'built': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'vault': str(vault),
        'corpus': corpus_hash,
        'builder': builder_hash(),
        'records_hash': records_hash,
        'documents': len(docs),
        'records': len(records),
        'citable': citable,
        'cite_kinds': cites,
        'tokens_total': sum(r['tokens'] for r in records),
        'by_kind': by_kind,
        'refused': [{'path': p, 'why': w} for p, w in sel.refusals],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                             encoding='utf-8', newline='\n')
    rep.say('ok', 'manifest.json  corpus %s, records %s' % (corpus_hash, records_hash))
    return 0


# --------------------------------------------------------------------------- main
def main() -> int:
    # The corpus is Russian. A console left on the Windows code page turns every
    # title in this report into question marks, which reads as a corrupted build.
    for stream_ in (sys.stdout, sys.stderr):
        try:
            stream_.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, OSError):
            pass
    ap = argparse.ArgumentParser(description='Build kb/ from a vault.')
    ap.add_argument('kb', help='a folder containing kb.toml')
    ap.add_argument('--out', default='')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--allow-shrink', action='store_true')
    args = ap.parse_args()

    kb_dir = Path(args.kb).resolve()
    cfg_path = kb_dir / 'kb.toml' if kb_dir.is_dir() else kb_dir
    if not cfg_path.exists():
        print('no kb.toml in %s.\n'
              'The build refuses to guess what may be answered from.' % kb_dir)
        return 1
    kb_dir = cfg_path.parent
    cfg = tomllib.loads(cfg_path.read_text('utf-8'))

    declared = cfg.get('vault', '')
    if not declared:
        print('kb.toml names no vault. Add:  vault = "<path>"')
        return 1
    vault = Path(declared).resolve()
    if not vault.is_dir():
        print('the vault named in kb.toml is not a folder: %s' % vault)
        return 1
    # A knowledge base that wrote into the vault it reads would make the vault a
    # function of its own index. It builds beside its own rules instead.
    out = Path(args.out).resolve() if args.out else kb_dir / 'kb'
    if out == vault or vault in out.parents:
        print('refusing to build inside the vault: %s' % out)
        return 1

    rep = Report()
    print('Solai   knowledge base, schema %d' % SCHEMA)
    print('  name   %s' % cfg.get('name', kb_dir.name))
    print('  vault  %s   (read only)' % vault)
    print('  rules  %s' % cfg_path)
    print('  out    %s%s' % (out, '   (dry run, nothing written)' if args.dry_run else ''))

    code = build(vault, cfg, out, rep, args.dry_run,
                 999.0 if args.allow_shrink else float(cfg.get('gates', {})
                                                       .get('max_shrink_pct', 10)))
    print('')
    done = 'reported.' if args.dry_run else 'built.'
    print('  refused to publish' if (code or rep.failed) else '  ' + done)
    return code or (1 if rep.failed else 0)


if __name__ == '__main__':
    sys.exit(main())
