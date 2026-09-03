# -*- coding: utf-8 -*-
"""How long the cards in one folder actually are, section by section.

    py _system/scripts/measure_cards.py <folder> [--json]

`.claude/skills/_shared/card-concision.md` tells every card skill to measure before cutting,
and until this shipped there was nothing to run: the instruction named a script the package
did not have. An instruction that cannot be followed is worse than no instruction, because
it is read every run and quietly teaches that the rules here are decorative (D1).

What it reports, per H2 section: how many cards carry it, and the median and maximum word
count of those that do. The median is the number to cut against. A single long card is not
evidence of anything - the distribution is - and a section that is long in one card and
absent in twenty is a different problem from one that is long in all twenty.

It measures and stops. It does not say which card is too long, because that is a judgement
about what the card has to carry, and `card-concision.md` already names the six kinds of
filler a cut has to be justified by.
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

H2 = re.compile(r'(?m)^##[ \t]+(.+?)[ \t]*$')


def split_fm(text):
    """Frontmatter is not prose and is not counted."""
    if not text.startswith('---'):
        return text
    nl = text.find('\n')
    if nl == -1 or text[3:nl].strip():
        return text
    end = text.find('\n---', nl)
    while end != -1:
        after = end + 4
        if after >= len(text) or text[after] in '\r\n':
            return text[after:].lstrip('\r\n')
        end = text.find('\n---', end + 1)
    return text


def words(chunk):
    """Words of prose. Table rows, code fences and callouts are structure, not length."""
    out = 0
    fenced = False
    for line in chunk.split('\n'):
        s = line.strip()
        if s.startswith('```'):
            fenced = not fenced
            continue
        if fenced or s.startswith(('|', '>')):
            continue
        out += len(s.split())
    return out


def sections(text):
    """Every H2 in one card, mapped to the word count of its body."""
    body = split_fm(text)
    marks = list(H2.finditer(body))
    out = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        out[m.group(1)] = words(body[m.end():end])
    return out


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return 0
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) // 2


def measure(folder):
    per_section, cards = {}, 0
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        for name in sorted(filenames):
            if not name.endswith('.md'):
                continue
            try:
                with io.open(os.path.join(dirpath, name), encoding='utf-8') as fh:
                    text = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            cards += 1
            for heading, n in sections(text).items():
                per_section.setdefault(heading, []).append(n)
    rows = [{'section': h, 'present': len(v), 'median': median(v), 'max': max(v)}
            for h, v in per_section.items()]
    rows.sort(key=lambda r: (-r['median'], r['section']))
    return cards, rows


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    folder = os.path.abspath(args[0]) if args else os.getcwd()
    if not os.path.isdir(folder):
        print('not a folder: %s' % folder)
        return 2
    cards, rows = measure(folder)
    if '--json' in sys.argv:
        print(json.dumps({'folder': folder, 'cards': cards, 'sections': rows},
                         ensure_ascii=False, indent=2))
        return 0
    print('cards %d   sections %d   (words of prose; tables, code and callouts excluded)'
          % (cards, len(rows)))
    if not cards:
        # D13: absence is a value. An empty folder reports as empty, not as zero-length.
        print('  nothing to measure. Cut nothing on the strength of this.')
        return 0
    print('  %-34s %7s %7s %7s' % ('section', 'present', 'median', 'max'))
    for r in rows:
        print('  %-34s %7d %7d %7d'
              % (r['section'][:34], r['present'], r['median'], r['max']))
    absent = [r for r in rows if r['present'] < cards]
    if absent:
        print('\n  A section missing from a card is not a short section. Absent from some:')
        for r in absent[:10]:
            print('    %-34s in %d of %d' % (r['section'][:34], r['present'], cards))
    return 0


if __name__ == '__main__':
    sys.exit(main())
