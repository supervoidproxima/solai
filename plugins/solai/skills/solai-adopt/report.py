# -*- coding: utf-8 -*-
"""Turn probe output into a conformance report a person can act on.

Six sections in a fixed order, and the last one is not optional.

    1  fingerprint       what this vault is, and the facts that decided it
    2  counts            what is actually here
    3  inferred model    the card classes as they exist, ready to become declarations
    4  conformance       rule by rule, with the evidence
    5  migration         ordered so the steps apply in sequence without conflict
    6  not checked       every rule this pass could not verify, and why
"""


def _t(headers, rows):
    if not rows:
        return '(none)'
    out = ['| ' + ' | '.join(str(h) for h in headers) + ' |',
           '| ' + ' | '.join('---' for _ in headers) + ' |']
    for r in rows:
        out.append('| ' + ' | '.join(str(c).replace('|', '\\|') for c in r) + ' |')
    return '\n'.join(out)


def render(d):
    c, p4, p5, p6, p7 = d['counts'], d['p4'], d['p5'], d['p6'], d['p7']
    L = []

    L.append('# Conformance report')
    L.append('')
    L.append('`%s`' % d['root'])
    L.append('')
    L.append('Read-only. Nothing in this vault was changed to produce this.')

    # 1 -----------------------------------------------------------------
    L.append('\n## 1. Fingerprint\n')
    L.append(_t(['What', 'Reading'], [
        ['observed governance tier', d['p2']['observed_tier']],
        ['proposed tier', '%s - %s' % (d['proposed_tier'], d['tier_reason'])],
        ['card classes in evidence', len(d['p3'])],
        ['already built by place', 'yes, this is an upgrade' if d['p9']['bond'] else 'no'],
    ]))
    gv = d['p2']
    if any(gv['files'].values()):
        L.append('')
        L.append('Governance files present: ' + ', '.join(
            '`%s`%s' % (k, ' (v%s)' % gv['versions'][k] if gv['versions'].get(k) else '')
            for k, v in gv['files'].items() if v))

    # 2 -----------------------------------------------------------------
    L.append('\n## 2. Counts\n')
    L.append('Counted before anything was judged.\n')
    L.append(_t(['What', 'Count'], [
        ['files', c['files']], ['markdown', c['md']], ['content markdown', c['content']],
        ['folders', c['folders']], ['with frontmatter', c['with_frontmatter']],
        ['distinct `type:` values', c['types']], ['cards in inferred classes', c['cards']],
        ['distinct frontmatter keys', len(p4['census'])],
        ['distinct tags in use', len(p5['used'])],
        ['change records', p6['records']],
        ['stamped generated files', d['p9']['stamped_files']],
    ]))

    # 3 -----------------------------------------------------------------
    L.append('\n## 3. Card classes as they exist\n')
    if not d['p3']:
        L.append('No card classes in evidence: no folder holds three or more files whose '
                 'names are identifiers. Nothing to infer, and nothing wrong with that.')
    else:
        L.append('Inferred from what is on disk, not from a template. A key present in 95% '
                 'or more of the sample is treated as required; a scalar with eight or fewer '
                 'distinct values across ten or more cards is treated as an enum. These are '
                 'proposals for declarations, not findings.\n')
        L.append(_t(['Prefix', 'Folder', 'Cards', '`type:`', 'Consistent', 'Statuses seen',
                     'Sequence holes'],
                    [[x['prefix'], '`%s/`' % x['folder'], x['cards'], x['type'] or '-',
                      'yes' if x['type_consistent'] else 'NO',
                      len(x['statuses']), x['id_hole_count']] for x in d['p3']]))
        for x in d['p3']:
            L.append('\n### %s (`%s/`)\n' % (x['prefix'], x['folder']))
            L.append('%d cards, %d sampled.\n' % (x['cards'], x['sampled']))
            L.append('- required: %s' % (', '.join('`%s`' % k for k in x['required']) or '-'))
            L.append('- optional: %s' % (', '.join('`%s`' % k for k in x['optional']) or '-'))
            if x['statuses']:
                L.append('- statuses in use: %s' % ', '.join(
                    '`%s` (%d)' % (k, v) for k, v in
                    sorted(x['statuses'].items(), key=lambda kv: -kv[1])))
            if x['enums']:
                L.append('- looks enumerated: %s' % '; '.join(
                    '`%s` = %s' % (k, ', '.join(v)) for k, v in sorted(x['enums'].items())))
            if x['id_hole_count']:
                L.append('- sequence holes: %s%s' % (
                    ', '.join('%03d' % h for h in x['id_holes']),
                    ' and %d more' % (x['id_hole_count'] - len(x['id_holes']))
                    if x['id_hole_count'] > len(x['id_holes']) else ''))

    # 4 -----------------------------------------------------------------
    L.append('\n## 4. Conformance\n')
    rows = []
    us = p4['underscore']
    rows.append(['frontmatter keys are kebab-case', 'no underscores',
                 '%d keys with underscores' % len(us),
                 'DIVERGES' if us else 'CONFORMS'])
    rows.append(['one concept, one key', 'no singular/plural pairs',
                 '%d pairs' % len(p4['plural_pairs']),
                 'DIVERGES' if p4['plural_pairs'] else 'CONFORMS'])
    rows.append(['tags come from a closed list',
                 'every tag declared',
                 ('%d of %d undeclared, list in %s'
                  % (len(p5['undeclared']), len(p5['used']),
                     ', '.join('`%s`' % s for s in p5.get('declared_in', []))))
                 if p5['declared'] else 'no declared list found',
                 'DIVERGES' if p5['undeclared'] else
                 ('CONFORMS' if p5['declared'] else 'ABSENT')])
    rows.append(['changes are recorded', 'a change folder with numbered records',
                 '%s, %d records' % (p6['folder'] or 'none', p6['records']),
                 'CONFORMS' if p6['records'] else 'ABSENT'])
    rows.append(['generated files carry a stamp', 'body-sha on every generated file',
                 '%d claim generation with no stamp' % len(d['p8']),
                 'DIVERGES' if d['p8'] else 'CONFORMS'])
    rows.append(['card type is consistent per folder', 'one `type:` per class',
                 '%d classes mixed' % len([x for x in d['p3'] if not x['type_consistent']]),
                 'DIVERGES' if any(not x['type_consistent'] for x in d['p3'])
                 else 'CONFORMS'])
    L.append(_t(['Rule', 'Expected', 'Found', 'Verdict'], rows))

    if us:
        L.append('\n**Keys with underscores**, with the first files they appear in:\n')
        L.append(_t(['Key', 'Files', 'Seen in'],
                    [['`%s`' % k, v, ', '.join('`%s`' % f for f in
                                               p4['underscore_files'].get(k, [])[:3])]
                     for k, v in sorted(us.items(), key=lambda kv: -kv[1])]))
    if p4['plural_pairs']:
        L.append('\n**Singular and plural of one key, both holding the same shape of value.** '
                 'Two names for one concept:\n')
        L.append(_t(['Plural', 'Singular', 'Plural files', 'Singular files', 'Shape'],
                    [[('`%s`' % a), ('`%s`' % b), ca, cb, sa]
                     for a, b, ca, cb, sa, sb in p4['plural_pairs']]))
    if p4.get('plural_ambiguous'):
        L.append('\n**Similar names holding different shapes.** Probably two concepts that '
                 'share a stem, such as a collection beside a pointer. Listed to be looked '
                 'at, not to be fixed:\n')
        L.append(_t(['Plural', 'Shape', 'Singular', 'Shape', 'Files'],
                    [[('`%s`' % a), sa, ('`%s`' % b), sb, '%d / %d' % (ca, cb)]
                     for a, b, ca, cb, sa, sb in p4['plural_ambiguous']]))
    if d['p8']:
        L.append('\n**Claims to be generated but carries no stamp:** ' +
                 ', '.join('`%s`' % x for x in d['p8'][:12]) +
                 (' and %d more' % (len(d['p8']) - 12) if len(d['p8']) > 12 else ''))
    if p5['undeclared']:
        L.append('\n**Tags in use but not declared:** ' +
                 ', '.join('`%s`' % t for t in p5['undeclared'][:20]))

    # 5 -----------------------------------------------------------------
    L.append('\n## 5. Migration, in an order that applies without conflict\n')
    steps, n = [], 0
    n += 1
    steps.append([n, 'adopt the declarations',
                  'write section 3 into `_system/os/classes/*.toml`, unchanged',
                  'additive; nothing existing is touched'])
    if us or p4['plural_pairs']:
        n += 1
        steps.append([n, 'normalise frontmatter keys',
                      'rename the keys in section 4 across every file',
                      'touches many files, changes no structure'])
    mixed = [x for x in d['p3'] if not x['type_consistent']]
    if mixed:
        n += 1
        steps.append([n, 'settle `type:` per class', 'one value per folder',
                      'affects %d classes' % len(mixed)])
    if d['p8']:
        n += 1
        steps.append([n, 'stamp the generated files',
                      'or stop calling them generated',
                      'makes a hand edit detectable from here on'])
    if not p5['declared']:
        n += 1
        steps.append([n, 'write the tag vocabulary from what is in use',
                      '%d tags, with counts' % len(p5['used']),
                      'records a set that already exists'])
    elif p5['undeclared']:
        n += 1
        steps.append([n, 'reconcile the tag vocabulary',
                      '%d of %d tags in use are not on the declared list: adopt them, or '
                      'retire them from the notes that carry them'
                      % (len(p5['undeclared']), len(p5['used'])),
                      'a closed list that most tags ignore is not closed'])
    n += 1
    steps.append([n, 'record the migration',
                  'one change record naming every step above', 'the amendment instrument'])
    L.append(_t(['#', 'Step', 'What', 'Cost'], steps))
    L.append('\nEach step is a proposal. Nothing runs until a tier is chosen and this map '
             'accepted, and then it applies as one change record.')

    # 6 -----------------------------------------------------------------
    L.append('\n## 6. Not checked\n')
    L.append('Mechanically out of reach for this pass. Listed because a conformance report '
             'without this section claims coverage it does not have.\n')
    L.append(_t(['What', 'Why not'], [[a, b] for a, b in d['not_checked']]))
    return '\n'.join(L) + '\n'
