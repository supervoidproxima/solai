# -*- coding: utf-8 -*-
"""25 assertions on the knowledge layer.

WHAT IS COVERED. A build over a small vault held in a temporary folder, end to end: what is
selected, what is refused and named, what lands on disk, and whether the same corpus rebuilds
to the same bytes. Then the four refusals the layer exists to make, the three the CLI makes
before it starts, and retrieval reading only the built `kb/`.

WHAT IS NOT, said here rather than implied by silence. The cloud placeholder gate cannot be
exercised: no test can create a file that Windows reports as living somewhere else, so the mask
and the position of the stage are asserted instead and the behaviour is not. The registry page
is not rendered here; it reads the same `records.jsonl` these assertions check and adds no gate
of its own. Nothing asserts that the selection rules select the right documents, which is a
human reading of the refusal list and is named as not checked in the skill file itself.
"""
import contextlib
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile

from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PKG, 'skills', 'solai-kb'))

import kb_ask as ASK                                                # noqa: E402
import kb_build as KB                                               # noqa: E402

EXPECTED = 25
NAME = 'kb'

IRD = (
    '---\n'
    'id: IRD-001\n'
    'type: ird\n'
    'title: Правила расчёта\n'
    '---\n'
    '\n'
    '## Часть 1. Общие положения\n'
    '\n'
    '### 1.1 Кассовый план ^a1b2c3\n'
    '\n'
    'Кассовый план формируется до 25 числа месяца. См. [[IRD-002|второй документ]].\n'
    '\n'
    '### 1.2 Сроки\n'
    '\n'
    'Сроки исчисляются в рабочих днях.\n'
)

TWIN = (
    '---\n'
    'id: IRD-001\n'
    'type: ird\n'
    'title: Правила расчёта, другая копия\n'
    '---\n'
    '\n'
    '## Часть 1\n'
    '\n'
    '### 1.1 Тот же пункт без якоря\n'
    '\n'
    'Текст без блочного якоря.\n'
)

GAP = (
    '---\n'
    'id: GAP-001\n'
    'type: gap\n'
    'status: open\n'
    'title: Разрыв в согласовании\n'
    '---\n'
    '\n'
    'Согласование идёт по почте, а норма требует системы.\n'
)

ARCHIVED = GAP.replace('GAP-001', 'GAP-009').replace('status: open', 'status: archived')


def rules():
    return {
        'name': 'test',
        'include': {'paths': ['sources/regulations/*.md', 'registry/**/*.md']},
        'exclude': {'paths': ['**/archive/**'], 'status': ['archived']},
        'granularity': {'clause': ['ird'], 'card': ['gap']},
        'chunk': {'max_chars': 1800},
    }


class Place(object):
    """A vault, a kb folder beside it, and nothing shared with the next test."""

    def __enter__(self):
        self.root = tempfile.mkdtemp(prefix='solai-kb-')
        self.vault = os.path.join(self.root, 'vault')
        self.kb = os.path.join(self.root, 'base')
        os.makedirs(os.path.join(self.vault, 'sources', 'regulations'))
        os.makedirs(os.path.join(self.vault, 'registry', 'gaps', 'archive'))
        os.makedirs(self.kb)
        self.write('sources/regulations/IRD-001.md', IRD)
        self.write('registry/gaps/GAP-001.md', GAP)
        self.write('registry/gaps/archive/GAP-009.md', ARCHIVED)
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self.root, ignore_errors=True)
        return False

    def write(self, rel, text):
        path = os.path.join(self.vault, *rel.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        io.open(path, 'w', encoding='utf-8', newline='\n').write(text)

    def out(self):
        return Path(self.kb) / 'kb'

    def build(self, dry=False, shrink=10.0, cfg=None):
        rep = KB.Report()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = KB.build(Path(self.vault), cfg or rules(), self.out(), rep, dry, shrink)
        return code, rep, buf.getvalue()

    def manifest(self):
        return json.loads((self.out() / 'manifest.json').read_text(encoding='utf-8'))

    def records(self):
        lines = (self.out() / 'records.jsonl').read_text(encoding='utf-8').splitlines()
        return [json.loads(x) for x in lines if x.strip()]


def run_cli(module, argv):
    buf = io.StringIO()
    keep = sys.argv
    sys.argv = argv
    try:
        with contextlib.redirect_stdout(buf):
            code = module.main()
    finally:
        sys.argv = keep
    return code, buf.getvalue()


def group_build(s):
    with Place() as p:
        code, rep, log = p.build(dry=True)
        s.ok('KB-01', 'a dry run reports and writes nothing',
             code == 0 and not rep.failed and not p.out().exists(),
             'exit %s, folder exists: %s' % (code, p.out().exists()))

        code, rep, log = p.build()
        names = sorted(x.name for x in p.out().iterdir()) if p.out().exists() else []
        s.eq('KB-02', 'a build writes the records, the documents, the index and the manifest',
             (code, rep.failed, names),
             (0, False, ['docs', 'index.sqlite', 'manifest.json', 'records.jsonl']))

        recs = p.records()
        clauses = [r for r in recs if r['kind'] == 'regulation.clause']
        cards = [r for r in recs if r['kind'] == 'card.gap']
        s.eq('KB-03', 'a regulation becomes one record per clause, a card exactly one record',
             (len(clauses), len(cards)), (2, 1))

        anchored = [r for r in clauses if r['anchor'] == 'a1b2c3']
        s.ok('KB-04', 'an anchored clause is citable by anchor and carries a deep link',
             len(anchored) == 1 and anchored[0]['cite_kind'] == 'anchor'
             and anchored[0]['link'] == '[[IRD-001#^a1b2c3|IRD-001]]',
             'got %r' % (anchored and {k: anchored[0][k]
                                       for k in ('cite_kind', 'link', 'cite')}))

        man = p.manifest()
        s.ok('KB-05', 'the manifest names the vault, the corpus and the builder',
             Path(man['vault']).resolve() == Path(p.vault).resolve()
             and len(man['corpus']) == 16 and man['builder'] == KB.builder_hash()
             and man['records'] == len(recs),
             'got vault %r corpus %r builder %r'
             % (man.get('vault'), man.get('corpus'), man.get('builder')))

        refused = {r['path']: r['why'] for r in man['refused']}
        s.ok('KB-06', 'every refused file is named with the reason it was refused',
             refused.get('registry/gaps/archive/GAP-009.md', '').startswith('exclude.paths'),
             'refused: %r' % refused)

        db = sqlite3.connect(str(p.out() / 'index.sqlite'))
        try:
            hits, whole = ASK.search(db, 'кассовый план', 6, {}, False)
        finally:
            db.close()
        s.ok('KB-07', 'the index answers a search over the text it indexed',
             bool(hits) and whole and hits[0]['id'] == 'IRD-001#^a1b2c3',
             'hits: %r' % hits[:1])


def group_provenance(s):
    with Place() as p:
        p.build()
        first = p.manifest()
        p.build()
        second = p.manifest()
        s.eq('KB-08', 'the same corpus and the same builder rebuild to the same bytes',
             (second['corpus'], second['records_hash'], second['records']),
             (first['corpus'], first['records_hash'], first['records']))

        def remanifest(**over):
            man = dict(p.manifest())
            man.update(over)
            (p.out() / 'manifest.json').write_text(
                json.dumps(man, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')

        remanifest(builder='0' * 12)
        code, rep, log = p.build()
        s.ok('KB-09', 'a changed builder is reported rather than refused',
             code == 0 and not rep.failed and 'the builder changed' in log,
             'exit %s' % code)

        remanifest(records=first['records'] - 1)
        code, rep, log = p.build()
        s.ok('KB-10', 'the same corpus and builder producing a different count is refused',
             code == 1 and 'identical input produced a different record count' in log,
             'exit %s' % code)

        remanifest(corpus='deadbeefdeadbeef', records=first['records'] * 4)
        code, rep, log = p.build()
        s.ok('KB-11', 'a collapse in the record count is refused, and names its own override',
             code == 1 and '--allow-shrink' in log, 'exit %s' % code)

        code, rep, log = p.build(shrink=999.0)
        s.ok('KB-12', 'the same collapse publishes when it is declared intended',
             code == 0 and not rep.failed, 'exit %s' % code)


def group_refusals(s):
    with Place() as p:
        # Two documents declaring one id: the last one read owns the text, and the records
        # of the first still claim an anchor it does not carry. The only way a dangling
        # anchor occurs in a real corpus, and the reason the gate is not decorative.
        p.write('sources/regulations/IRD-001z.md', TWIN)
        code, rep, log = p.build()
        s.ok('KB-13', 'a record claiming an anchor its document does not carry is refused',
             code == 1 and 'claim an anchor their document does not contain' in log
             and not p.out().exists(),
             'exit %s, wrote: %s' % (code, p.out().exists()))

    s.eq('KB-14', 'the placeholder mask covers all three cloud attributes',
         KB.PLACEHOLDER_MASK, 0x1000 | 0x40000 | 0x400000)

    src = io.open(os.path.join(PKG, 'skills', 'solai-kb', 'kb_build.py'),
                  encoding='utf-8').read()
    s.ok('KB-15', 'nothing is read until every selected file is known to be on this disk',
         src.index("rep.stage('materialised')") < src.index("rep.stage('records')"),
         'a placeholder read after records are built is a corpus that looks present and is empty')

    with Place() as p:
        code, log = run_cli(KB, ['kb_build.py', p.kb])
        s.ok('KB-16', 'a kb folder with no rules file is refused by name',
             code == 1 and 'no kb.toml' in log, log[:200])

        io.open(os.path.join(p.kb, 'kb.toml'), 'w', encoding='utf-8').write('name = "test"\n')
        code, log = run_cli(KB, ['kb_build.py', p.kb])
        s.ok('KB-17', 'a rules file naming no vault is refused by name',
             code == 1 and 'names no vault' in log, log[:200])

        io.open(os.path.join(p.kb, 'kb.toml'), 'w', encoding='utf-8').write(
            'vault = "%s"\n' % p.vault.replace('\\', '/'))
        code, log = run_cli(KB, ['kb_build.py', p.kb, '--out',
                                 os.path.join(p.vault, 'kb')])
        s.ok('KB-18', 'an output that would land inside the vault is refused',
             code == 1 and 'refusing to build inside the vault' in log, log[:200])


def group_ask(s):
    with Place() as p:
        p.build()
        code, log = run_cli(ASK, ['kb_ask.py', p.kb, 'кассовый план'])
        s.ok('KB-19', 'retrieval finds the clause and prints the citation for it',
             code == 0 and 'IRD-001, п. 1.1' in log, log[:300])

        code, log = run_cli(ASK, ['kb_ask.py', p.kb, 'кассовый план', '--prompt'])
        s.ok('KB-20', 'the prompt block carries the rule that Unknown is a correct answer',
             code == 0 and 'Unknown' in log and 'ВОПРОС:' in log, log[:300])

        code, log = run_cli(ASK, ['kb_ask.py', p.kb, 'совершенно посторонний вопрос'])
        s.ok('KB-21', 'a corpus with no answer says so rather than returning its best guess',
             code == 0 and 'Ничего не найдено' in log, log[:300])

        shutil.rmtree(p.vault)
        code, log = run_cli(ASK, ['kb_ask.py', p.kb, 'кассовый план'])
        s.ok('KB-22', 'the vault is not read: retrieval works with the vault gone',
             code == 0 and 'IRD-001' in log, log[:300])


def group_surface(s):
    skill = os.path.join(PKG, 'skills', 'solai-kb', 'SKILL.md')
    text = io.open(skill, encoding='utf-8').read() if os.path.exists(skill) else ''
    s.ok('KB-23', 'the layer has a skill surface that declares how it is reached',
         text.startswith('---\nname: solai-kb\n') and '/solai kb' in text
         and 'permissions:' in text,
         'D1: a capability nothing routes to is a capability the package cannot show')

    example = os.path.join(PKG, 'skills', 'solai-kb', 'kb.example.toml')
    try:
        import tomllib
        cfg = tomllib.loads(io.open(example, encoding='utf-8').read())
    except Exception as err:                                        # noqa: BLE001
        cfg = {'error': str(err)}
    s.ok('KB-24', 'the exemplar the skill names exists and parses',
         'vault' in cfg and 'paths' in cfg.get('include', {}),
         'D18: every artefact type names a live exemplar. Got %r' % sorted(cfg))

    stale = []
    for name in ('README.md', 'ARCHITECTURE.md'):
        body = io.open(os.path.join(PKG, name), encoding='utf-8').read()
        if 'unreachable' in body or 'No skill surface yet' in body:
            stale.append(name)
    s.eq('KB-25', 'no document still describes the layer as unreachable', stale, [])


GROUPS = (group_build, group_provenance, group_refusals, group_ask, group_surface)
