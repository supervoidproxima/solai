# -*- coding: utf-8 -*-
"""13 assertions on the stamp an HTML page carries, and on both halves reading one rule.

WHAT THEY GUARD. `GAP-016`: the dashboard computed its own digest, printed it as bare text, and
was read by nothing, in every vault this package has ever built. Two halves were broken and
fixing either alone would have changed nothing, so `PS-11` and `PS-12` hold the pair rather than
the parts: the generator emits a stamp this reader finds, and the reader walks the extension the
generator writes.

`PS-05` is the one that keeps it true rather than true today. The digest is taken over the
document with its own digest BLANKED, because a file cannot contain the hash of itself. The first
version hashed a document carrying a `__STAMPLINE__` placeholder, which only the writer can
reproduce, and the first draft of the fix put the digest in the footer as well and filled that in
after signing, which changed the document after its hash was taken. Both are the same mistake and
`PS-05` and `PS-06` are what catch it.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
RUNTIME = os.path.join(PKG, 'runtime')
if RUNTIME not in sys.path:
    sys.path.insert(0, RUNTIME)

import _pagestamp as P                                              # noqa: E402

EXPECTED = 13
NAME = 'pagestamp'

PAGE = '<html><body>one</body>\n' + (P.STAMP % ('gen_dashboard', '')) + '\n</html>\n'


def group_rule(s):
    """The stamp itself: writing one, reading one back, and what voids it."""
    signed = P.sign(PAGE, 'gen_dashboard')
    declared, actual = P.read(signed)

    s.eq('PS-01', 'a signed page reads back as what it says it is', declared, actual)

    s.ok('PS-02', 'the digest is 16 hex characters, the width every other stamp here uses',
         len(declared) == 16 and all(c in '0123456789abcdef' for c in declared), declared)

    tampered = signed.replace('one', 'two')
    d2, a2 = P.read(tampered)
    s.ok('PS-03', 'a hand edit to the page voids the stamp, which is the whole job',
         d2 != a2 and d2 == declared, repr((d2, a2)))

    s.eq('PS-04', 'a page carrying no stamp reads None, which is not the same claim as a '
                  'digest that fails to match',
         P.read('<html>nothing generated here</html>'), None)

    # The property the whole shape turns on, and the one got wrong twice.
    s.ok('PS-05', 'the digest is taken over the page with its own digest blanked, so a reader '
                  'holding the finished file can reproduce it without knowing the writer\'s '
                  'placeholder',
         P.body_sha(signed) == P.body_sha(PAGE) == declared,
         'a file cannot contain the hash of itself; blanking is symmetric, a placeholder is not')

    s.ok('PS-06', 'signing is the last thing done to a page: signing twice changes nothing',
         P.sign(signed, 'gen_dashboard') == signed,
         'anything written after the signature is outside the document that was hashed')

    s.ok('PS-07', 'line endings and trailing whitespace are not content, on both sides',
         P.body_sha(signed.replace('\n', '\r\n')) == declared
         and P.body_sha(signed.replace('</html>', '</html>   ')) == declared)

    s.raises('PS-08', 'signing a page whose template carries no stamp is refused by name, '
                      'rather than quietly producing an unstamped page',
             lambda: P.sign('<html>no stamp here</html>', 'gen_dashboard'),
             naming=('gen_dashboard', 'solai:generated-by'), exc=ValueError)

    # The Counselor's site pages carry `page=` and `inputs=` between the name and the digest.
    # One reader covers both shapes, or this package grows the second family it keeps removing.
    rich = ('<html>a<!-- solai:generated-by build_site page=index inputs=abc123 body= -->'
            '</html>')
    try:
        rich = P.sign(rich, 'build_site')
        got = P.read(rich)
    except ValueError as err:                                       # a pattern that cannot see it
        got = ('refused: %s' % err, None)
    s.ok('PS-09', 'a richer stamp naming a page and its inputs is read by the same pattern',
         got is not None and got[0] == got[1] and len(got[0] or '') == 16, repr(got))

    s.ok('PS-10', 'two pages differing only in their body get different digests',
         P.body_sha(P.sign(PAGE, 'g')) != P.body_sha(P.sign(PAGE.replace('one', 'two'), 'g')))


def group_both_halves(s):
    """The pair. Fixing either alone would have left the dashboard exactly as unchecked."""
    gen = io.open(os.path.join(RUNTIME, 'gen_dashboard.py'), encoding='utf-8').read()
    chk = io.open(os.path.join(RUNTIME, 'stamp_check.py'), encoding='utf-8').read()

    s.ok('PS-11', 'the generator signs through the shared module rather than printing a digest '
                  'of its own',
         '_pagestamp.sign(' in gen and 'import _pagestamp' in gen
         and 'hashlib' not in gen,
         'a digest computed beside the rule is the defect this module exists to end')

    s.ok('PS-12', 'the checker walks .html and reads the stamp through the same module',
         "'.html'" in chk and '_pagestamp.read(' in chk and 'import _pagestamp' in chk,
         'the generator emitting a stamp nothing walks is half a fix')

    manifests = [f for f in os.listdir(os.path.join(PKG, 'archetypes'))]
    missing = []
    for a in manifests:
        p = os.path.join(PKG, 'archetypes', a, 'manifest.toml')
        if os.path.isfile(p) and '_pagestamp.py' not in io.open(p, encoding='utf-8').read():
            missing.append(a)
    s.eq('PS-13', 'every archetype ships the module, or the vaults that take this release get '
                  'a checker that cannot import what it needs', missing, [])


GROUPS = (group_rule, group_both_halves)
