# -*- coding: utf-8 -*-
"""Assertions over `install.ps1`, the one part of this project with no gate of its own.

The package has 239 assertions and the installer had none, which is backwards: the package
is exercised on every run and the installer runs once per machine, on a machine nobody is
watching, in a state nobody here can reproduce. Four defects have already been found in it
by hand. These are the ones a machine can find again.

WHY THIS IS A SEPARATE COMMAND. `install.ps1` sits at the repository root, outside the
plugin, so a marketplace install does not carry it. Folding these into `run_tests.py` would
make the 239 depend on a file that is legitimately absent half the time; `verify_engine.py`
set the precedent for a second gate with its own command.

WHY IT IS SAFE TO RUN. Every invocation passes `-DryRun`, which returns at stage 0 before
anything is installed, fetched or written. The helper functions are defined above that
return, so dot-sourcing the script defines them and then stops, which is how `Invoke-Native`
and `Have` are tested against the real definitions rather than a copy of them.

WHAT IT CANNOT DO. It cannot prove the installer works on a bare machine. Stages 1 to 8
never execute here. This suite covers stage 0, the helpers, and the promise that a dry run
writes nothing; the rest needs a machine that has nothing, and that is recorded as
outstanding rather than implied.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PKG))
INSTALLER = os.path.join(REPO, 'install.ps1')

sys.path.insert(0, HERE)
from harness import Suite                                           # noqa: E402

EXPECTED = 17
NAME = 'install'

PS = 'powershell'


# --------------------------------------------------------------------------- running

def run_ps(script, env=None, timeout=180):
    """Run a PowerShell snippet with a controlled environment."""
    base = dict(os.environ)
    base['SOLAI_TEST'] = '1'
    for k, v in (env or {}).items():
        if v is None:
            base.pop(k, None)
        else:
            base[k] = v
    proc = subprocess.run(
        [PS, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', script],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        env=base, timeout=timeout, cwd=REPO)
    return proc.returncode, (proc.stdout or '') + (proc.stderr or '')


def dry_run(env=None):
    """A dry run of the real installer. Returns (exit code, combined output)."""
    return run_ps('& "%s" -DryRun' % INSTALLER, env)


def bare_profile():
    """A profile directory with nothing in it, and a PATH with nothing on it.

    Stage 0 derives every path it inspects from USERPROFILE and resolves every tool through
    PATH, so pointing both somewhere empty is what a bare machine looks like from inside the
    script. The OneDrive variables are cleared for the same reason.
    """
    root = tempfile.mkdtemp(prefix='solai-bare-')
    empty = os.path.join(root, 'nopath')
    os.makedirs(empty)
    return root, {
        'USERPROFILE': root,
        'PATH': empty,
        'OneDrive': None,
        'OneDriveCommercial': None,
    }


def tree(path):
    out = []
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            full = os.path.join(dirpath, f)
            try:
                out.append((os.path.relpath(full, path), os.path.getsize(full)))
            except OSError:
                pass
    return sorted(out)


def bare_counts(body):
    """Lines where .Count is read off a parenthesised command rather than an @() array."""
    bad = []
    for i, line in enumerate(body.splitlines(), 1):
        col = line.find(').Count')
        while col != -1:
            depth, j = 0, col
            while j >= 0:
                if line[j] == ')':
                    depth += 1
                elif line[j] == '(':
                    depth -= 1
                    if depth == 0:
                        break
                j -= 1
            if j > 0 and line[j - 1] != '@':
                bad.append('line %d' % i)
            col = line.find(').Count', col + 1)
    return bad


# --------------------------------------------------------------------------- groups

def group_shape(s):
    s.ok('IN-01', 'the installer is where the published one-liner fetches from',
         os.path.isfile(INSTALLER), INSTALLER)

    code, out = run_ps(
        '$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('
        '"%s",[ref]$null,[ref]$e); if($e){$e|ForEach-Object{$_.Message}}else{"PARSE-OK"}'
        % INSTALLER)
    s.contains('IN-02', 'it parses as PowerShell', out, 'PARSE-OK')

    body = open(INSTALLER, encoding='utf-8').read()
    s.ok('IN-03', 'the stage counter matches the eight stages it documents',
         '$script:Total   = 8' in body or '$script:Total = 8' in body,
         'the summary numbers every stage against this total')
    s.ok('IN-04', 'every documented switch is a real parameter',
         all(('[switch] $' + n) in body for n in ('DryRun', 'SkipApps', 'PublicOnly', 'NoHandoff')))

    # The script runs under Set-StrictMode -Version Latest, where .Count on a scalar or on
    # nothing is a reference to a property that is not there, and terminating. A command in
    # parentheses returns a scalar for one result and $null for none, so `(cmd ...).Count` is
    # correct only on a machine that happens to return two or more. That is why this is static
    # and not behavioural: the failing case is a fresh machine, which no dry run reproduces.
    s.ok('IN-17', 'every .Count on a command result is wrapped in @()',
         not bare_counts(body),
         'unwrapped: ' + ', '.join(bare_counts(body)) if bare_counts(body) else
         'a scalar result would otherwise terminate the run')


def group_dry_run(s):
    code, out = dry_run()
    s.eq('IN-05', 'a dry run on this machine exits clean', code, 0)
    s.contains('IN-06', 'a dry run says it wrote nothing', out, 'Nothing was written')
    s.ok('IN-07', 'a dry run never reaches the installing stages',
         '[1/8] applications' not in out,
         'stage 1 would install; the dry run returns before it')

    _, again = dry_run()
    s.eq('IN-08', 'two dry runs report the same thing', out.strip(), again.strip())


def group_bare(s):
    root, env = bare_profile()
    try:
        before = tree(root)
        code, out = dry_run(env)

        s.ok('IN-09', 'a bare profile does not crash the script',
             'Exception' not in out and 'ParserError' not in out, out[-400:])
        s.ok('IN-10', 'a bare machine is told what it is missing, by name',
             'missing' in out.lower() or 'not on PATH' in out, out[-400:])
        # The contract changed under this assertion and the assertion did not follow. winget
        # ships with App Installer, so it can be installed and unreachable at once; stage 0 now
        # recovers it from the app-execution-alias directory instead of stopping to say it is
        # missing, and the stop fires only on a machine that genuinely does not have it. What
        # is still gated is that the outcome is NAMED either way, never a stack trace: the
        # directory it was recovered from, or App Installer as the thing to go and install.
        named = ('winget found at', 'winget was installed but not on PATH',
                 'would put winget on your PATH', 'App Installer')
        s.ok('IN-11', 'winget is either recovered by name or named as the one stop',
             'winget' in out and any(n in out for n in named),
             'the one dependency the script cannot install for you')
        s.eq('IN-12', 'a dry run writes nothing into the profile it inspects',
             tree(root), before)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def group_helpers(s):
    """Dot-source with -DryRun: the functions are defined, then the script returns."""
    probe = (
        '. "%s" -DryRun *> $null; '
        # A native command that writes to stderr and fails. On a fresh Windows the Python
        # launcher does exactly this, and under a strict ErrorActionPreference it became a
        # terminating error that killed stage 0 on the first machine that ran it.
        '$noisy = Join-Path $env:TEMP "solai-noisy.cmd"; '
        '@("@echo off", "echo something on stderr 1>&2", "exit /b 3") | Set-Content $noisy -Encoding ASCII; '
        # Under Stop, which is what the failing machine was running, a native command writing
        # to stderr is a terminating error unless Invoke-Native neutralises it. Calling this
        # without setting Stop would assert nothing: the default is Continue, which passes
        # whether the guard is there or not.
        '$ErrorActionPreference = "Stop"; '
        '$text = Invoke-Native $noisy; '
        'Write-Output ("SURVIVED=" + $true); '
        'Write-Output ("EXIT=" + $script:NativeExit); '
        'Write-Output ("SAW=" + $(if ($text -match "stderr") { "yes" } else { "no" })); '
        'Write-Output ("HAVE_REAL=" + (Have "powershell")); '
        'Write-Output ("HAVE_FAKE=" + (Have "solai-not-a-command-xyz")); '
        'Remove-Item $noisy -ErrorAction SilentlyContinue'
    ) % INSTALLER
    code, out = run_ps(probe)

    s.contains('IN-13', 'a command that writes to stderr does not terminate the run',
               out, 'SURVIVED=True')
    s.contains('IN-14', 'the exit code of a failing command is reported, not swallowed',
               out, 'EXIT=3')
    s.ok('IN-15', 'stderr is captured rather than lost', 'SAW=yes' in out, out[-300:])
    s.ok('IN-16', 'a tool on PATH is found and one that is absent is not',
         'HAVE_REAL=True' in out and 'HAVE_FAKE=False' in out, out[-300:])


GROUPS = (group_shape, group_dry_run, group_bare, group_helpers)


def main():
    if not os.path.isfile(INSTALLER):
        print('  install.ps1 not found at %s' % INSTALLER)
        print('  This gate covers the repository, not the plugin. SKIPPED.')
        return 0
    suite = Suite(NAME, EXPECTED)
    for group in GROUPS:
        suite.group(group)
    head, lines = suite.report()
    print('')
    print('  ' + head)
    if lines:
        print(lines)
    print('')
    print('  ' + ('INSTALL GATE GREEN' if suite.green() else 'INSTALL GATE RED'))
    return 0 if suite.green() else 1


if __name__ == '__main__':
    sys.exit(main())
