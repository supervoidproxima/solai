# -*- coding: utf-8 -*-
"""The assertion-counting harness. No third-party dependency, by the same rule as `lib/`.

`unittest` counts test FUNCTIONS; this package's gate is stated in ASSERTIONS (45 on the
primitives, 39 on the declaration loader, 84 total). A harness that reports a different
number than the gate is a harness whose green light has to be translated before it can be
trusted, so this one counts the same unit the gate names.

Every assertion carries a stable id (`FM-04`, `DA-11`). An id is how a failure is discussed
without pasting a traceback, and how a later change proves it did not quietly drop a check:
the runner refuses a run whose assertion count does not match the declared expectation, so
deleting an assertion fails the suite exactly as loudly as breaking one.

A group that crashes records ONE failure and keeps going. The alternative - letting the
exception out - costs every assertion after it in the file, and a suite that reports 12 of 84
because of one typo tells you nothing about the other 72.
"""
import traceback


class Suite(object):

    def __init__(self, name, expected):
        self.name = name
        self.expected = expected
        self.results = []                 # (id, label, passed, detail)

    # ------------------------------------------------------------------ assertions

    def ok(self, aid, label, cond, detail=''):
        cond = bool(cond)
        self.results.append((aid, label, cond, '' if cond else (detail or 'condition was false')))
        return cond

    def eq(self, aid, label, got, want):
        return self.ok(aid, label, got == want, 'got %r, want %r' % (got, want))

    def contains(self, aid, label, haystack, needle):
        return self.ok(aid, label, needle in haystack,
                       '%r not found in %r' % (needle, _clip(haystack)))

    def raises(self, aid, label, fn, naming=(), exc=Exception):
        """Assert fn() raises, and that the message NAMES each string in `naming`.

        Naming is checked, not just the raise: a loader that fails for the wrong reason is
        indistinguishable from one that fails for the right reason until the day the reason
        matters. `DeclError` collects every reason at once, so its `.errors` is joined first.
        """
        if isinstance(naming, str):
            naming = (naming,)
        try:
            fn()
        except exc as err:
            msg = '\n'.join(getattr(err, 'errors', ())) or str(err)
            missing = [n for n in naming if n not in msg]
            return self.ok(aid, label, not missing,
                           'raised, but the message does not name %r. Message: %s'
                           % (missing, _clip(msg)))
        except Exception as err:                                    # noqa: BLE001
            return self.ok(aid, label, False,
                           'raised %s, expected %s: %s' % (type(err).__name__, exc.__name__, err))
        return self.ok(aid, label, False, 'did not raise')

    def accepts(self, aid, label, fn):
        """Assert fn() does NOT raise. The negative cases need a positive twin or the
        loader could pass every one of them by refusing everything."""
        try:
            fn()
        except Exception as err:                                    # noqa: BLE001
            msg = '\n'.join(getattr(err, 'errors', ())) or str(err)
            return self.ok(aid, label, False, 'raised %s: %s' % (type(err).__name__, _clip(msg)))
        return self.ok(aid, label, True)

    # ------------------------------------------------------------------ running

    def group(self, fn):
        try:
            fn(self)
        except Exception:                                           # noqa: BLE001
            self.results.append(('%s' % fn.__name__, 'group crashed before finishing',
                                 False, traceback.format_exc()))

    @property
    def passed(self):
        return sum(1 for r in self.results if r[2])

    @property
    def failed(self):
        return [r for r in self.results if not r[2]]

    @property
    def ran(self):
        return len(self.results)

    def duplicate_ids(self):
        seen, dupes = set(), []
        for aid, _, _, _ in self.results:
            if aid in seen:
                dupes.append(aid)
            seen.add(aid)
        return dupes

    def report(self):
        lines = []
        for aid, label, passed, detail in self.results:
            if not passed:
                lines.append('  FAIL  %-8s %s' % (aid, label))
                for ln in detail.rstrip().split('\n'):
                    lines.append('        %s' % ln)
        head = '%-14s %d/%d passed' % (self.name, self.passed, self.ran)
        if self.ran != self.expected:
            head += '   [expected %d assertions, %d ran]' % (self.expected, self.ran)
        dupes = self.duplicate_ids()
        if dupes:
            head += '   [duplicate ids: %s]' % ', '.join(sorted(set(dupes)))
        return head, '\n'.join(lines)

    def green(self):
        return not self.failed and self.ran == self.expected and not self.duplicate_ids()


def _clip(text, n=400):
    text = str(text).replace('\n', ' | ')
    return text if len(text) <= n else text[:n] + '...'
