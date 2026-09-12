# -*- coding: utf-8 -*-
"""The one argument reader every script in this folder uses, so the rule is spelled once.

WHY THIS EXISTS. The seeded `readme.md` states the convention: the vault root is `argv[1]`.
Nine scripts shipped without honouring it, in two different ways, because the rule was written
nine times and drifted twice. Two took `argv[1]` unconditionally, so `mint_change.py --help`
created a directory named `--help` and claimed `CHG-001` inside it. Seven filtered out anything
starting with `--` and fell back to the working directory, so `gen_dashboard.py --check`
discarded the flag and wrote the dashboard anyway, and `validate_cards.py --help` reported
`BLOCKER 0` over a folder it had never read. All three exited 0.

WHAT IT GUARANTEES, and it is narrower than the sentence it replaces. Not that nothing writes:
a generator's whole job is to write, and `mint_change.py`'s write IS its claim. What it
guarantees is that **an invocation the script does not understand is refused rather than
performed**. That is enforceable, and a promise nobody can keep is worse than a narrower one
everybody can.

WHY IT RETURNS RATHER THAN EXITS. The refusal text is the product here, and a function that
calls `sys.exit` can only be tested by catching an exception and capturing a stream. This one
hands the caller an exit code and a message, which an assertion can read directly. It is the
same reason `--plan` is the default everywhere: the thing that decides is separated from the
thing that acts.
"""
import os

USAGE_EXIT = 2


def parse(argv, usage, flags=(), values=(), default_root='.'):
    """-> (root, opts, done).

    `flags`   options that stand alone, e.g. `--json`
    `values`  options that consume the next argument, e.g. `--title`

    `done` is None to proceed, or `(exit_code, message)` for the caller to print and return.
    `opts` holds every declared option: a flag as True or False, a value as its string or None.

    The root is the first argument that is not an option, absolute. A second one is refused:
    every script here takes exactly one, and an unquoted title arriving as a stray positional
    is the mistake this catches. `default_root=None` makes the path required rather than
    defaulting to the working directory, which is right for a script that writes.
    """
    flags, values = tuple(flags), tuple(values)
    opts = dict([(f, False) for f in flags] + [(v, None) for v in values])
    positional = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ('--help', '-h'):
            return None, opts, (0, usage)
        if a in flags:
            opts[a] = True
        elif a in values:
            if i + 1 >= len(argv):
                return None, opts, (USAGE_EXIT, "%s needs a value.\n\n%s" % (a, usage))
            opts[a] = argv[i + 1]
            i += 1
        elif a.startswith('-') and a != '-':
            known = ', '.join(sorted(flags + values)) or 'none'
            return None, opts, (USAGE_EXIT,
                                "unknown option %s. This script accepts: %s.\n\n%s"
                                % (a, known, usage))
        else:
            positional.append(a)
        i += 1

    if len(positional) > 1:
        return None, opts, (USAGE_EXIT,
                            "one path, not %d: %s. Quote an argument that contains spaces."
                            "\n\n%s" % (len(positional), ', '.join(positional), usage))

    if not positional and default_root is None:
        return None, opts, (USAGE_EXIT, usage)

    root = os.path.abspath(positional[0] if positional else default_root)
    return root, opts, None
