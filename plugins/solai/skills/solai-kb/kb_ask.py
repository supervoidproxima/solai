#!/usr/bin/env python3
"""Ask a knowledge base a question.

    py kb_ask.py <kb-folder> "вопрос" [--type ird] [--k 6] [--prompt] [--json]

Retrieval only. It finds the passages and formats them so that an answer built on
them can be checked; it does not write the answer. Whatever writes the answer gets
the block from --prompt, and that block carries the one standing rule: every claim
names a record, and Unknown is a correct answer.

Reads only the built kb/. The vault is not touched and does not need to be here.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

WORD_RE = re.compile(r'[0-9A-Za-zА-Яа-яЁё_-]{2,}')

RULES = (
    'Отвечай только на основании фрагментов ниже.\n'
    'Каждое утверждение сопровождай ссылкой на источник в квадратных скобках: [IRD-007, п. 4.2].\n'
    'Если во фрагментах нет ответа, напиши одно слово: Unknown. Не додумывай.\n'
    'Если фрагменты противоречат друг другу, покажи оба и назови расхождение.'
)


def stems(question: str, exact: bool) -> list[str]:
    """Crude stemming, because FTS5 does not decline Russian.

    A search for "кассовый план" must find "кассового плана", and unicode61 will
    not do that on its own. Cutting the tail off a long word and matching by
    prefix costs some precision and buys most of the recall back. It is the first
    thing to replace when the question log says retrieval is missing things.
    """
    out = []
    for w in WORD_RE.findall(question.lower()):
        if exact or len(w) < 4:
            out.append('"%s"' % w)
        elif len(w) >= 6:
            out.append('%s*' % w[:-3])
        else:
            out.append('%s*' % w)
    return out


def search(db: sqlite3.Connection, question: str, k: int, where: dict,
           exact: bool) -> tuple[list[dict], bool]:
    terms = stems(question, exact)
    if not terms:
        return [], False
    clauses, params = [], []
    for col, val in where.items():
        if val:
            clauses.append('fa.%s = ?' % col)
            params.append(val)
    filt = (' AND ' + ' AND '.join(clauses)) if clauses else ''

    # Implicit AND first, because a question's words usually belong together.
    # If nothing carries all of them, widen to OR rather than return nothing.
    for whole, match in ((True, ' '.join(terms)), (False, ' OR '.join(terms))):
        rows = db.execute(
            'SELECT f.id, fa.title, fa.path, fa.doc_type, bm25(fts) AS score '
            'FROM fts f JOIN facet fa ON fa.id = f.id '
            'WHERE fts MATCH ?%s ORDER BY score LIMIT ?' % filt,
            [match] + params + [k]).fetchall()
        if rows:
            return ([{'id': r[0], 'title': r[1], 'path': r[2],
                      'type': r[3], 'score': r[4]} for r in rows], whole)
    return [], False


def load_records(kb: Path) -> dict:
    recs = {}
    with open(kb / 'records.jsonl', encoding='utf-8') as fh:
        for line in fh:
            r = json.loads(line)
            recs[r['id']] = r
    return recs


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(description='Ask a built knowledge base.')
    ap.add_argument('kb')
    ap.add_argument('question')
    ap.add_argument('--k', type=int, default=6)
    ap.add_argument('--type', default='', help='doc_type, e.g. ird, gap, resolution')
    ap.add_argument('--status', default='')
    ap.add_argument('--exact', action='store_true', help='no prefix stemming')
    ap.add_argument('--prompt', action='store_true', help='emit a block ready to answer from')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    kb = Path(args.kb).resolve()
    kb = kb / 'kb' if (kb / 'kb' / 'index.sqlite').exists() else kb
    if not (kb / 'index.sqlite').exists():
        print('no index at %s. Build it first with kb_build.py.' % kb)
        return 1

    db = sqlite3.connect('file:%s?mode=ro' % (kb / 'index.sqlite').as_posix(), uri=True)
    hits, whole = search(db, args.question, args.k,
                         {'doc_type': args.type, 'status': args.status}, args.exact)
    if not hits:
        print('Ничего не найдено. Это тоже ответ: корпус не содержит подходящего фрагмента.')
        return 0

    recs = load_records(kb)
    picked = [recs[h['id']] for h in hits if h['id'] in recs]
    budget = sum(r['tokens'] for r in picked)

    if args.json:
        print(json.dumps(picked, ensure_ascii=False, indent=2))
        return 0

    if args.prompt:
        print(RULES)
        if not whole:
            print('\nВНИМАНИЕ: ни один фрагмент не содержит всех слов вопроса. '
                  'Ниже частичные совпадения. Скорее всего верный ответ - Unknown.')
        print('\nВОПРОС: %s\n' % args.question)
        for r in picked:
            print('--- [%s]' % r['cite'])
            print(r['breadcrumb'])
            print(r['text'])
            print('')
        print('(%d фрагментов, ~%d токенов)' % (len(picked), budget))
        return 0

    print('\n%s' % args.question)
    print('%d passages, ~%d tokens%s\n'
          % (len(picked), budget,
             '' if whole else '   PARTIAL: no passage carried every word'))
    for r, h in zip(picked, hits):
        print('  [%s]  %s' % (r['cite'], r['breadcrumb']))
        body = ' '.join(r['text'].split())
        print('      %s%s' % (body[:220], '…' if len(body) > 220 else ''))
        print('      %s · %d tokens · %s' % (r['path'], r['tokens'],
                                             r['link'] or 'no deep link'))
        print('')
    return 0


if __name__ == '__main__':
    sys.exit(main())
