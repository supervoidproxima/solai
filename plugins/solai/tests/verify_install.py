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

EXPECTED = 28
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


def field(out, key):
    """The value a probe printed as `KEY=value`, or '' if it never printed one."""
    for line in out.splitlines():
        if line.startswith(key + '='):
            return line[len(key) + 1:].strip()
    return ''


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


def group_timed(s):
    """Invoke-NativeTimed, the helper that runs winget on a deadline.

    Dot-sourced like `group_helpers`, and against the real definition for the same reason: a
    copy of a helper passes long after the original has stopped agreeing with it. The exit
    code is what every assertion here is really about. A background job reports its own
    state, and a native command that fails leaves that state 'Completed' all the same, so a
    helper that reads state as success reports an install that never happened.
    """
    probe = (
        '. "%s" -DryRun *> $null; '
        '$ok = Invoke-NativeTimed -Exe "cmd.exe" -TimeoutSec 60 -Arguments @("/c","echo hello"); '
        'Write-Output ("EXITOK=" + $script:NativeExit); '
        'Write-Output ("OUTOK=" + $ok); '
        # 1602 is the code winget returns when the elevation prompt is dismissed, which stage 1
        # tells the reader how to recover from. It is a plain non-zero exit, not an error: the
        # job finishes tidily and says nothing about it.
        '$null = Invoke-NativeTimed -Exe "cmd.exe" -TimeoutSec 60 -Arguments @("/c","exit 1602"); '
        'Write-Output ("EXIT1602=" + $script:NativeExit); '
        '$t = Get-Date; '
        '$slow = Invoke-NativeTimed -Exe "cmd.exe" -TimeoutSec 3 -Arguments @("/c","ping -n 30 127.0.0.1 >nul"); '
        'Write-Output ("EXITSLOW=" + $script:NativeExit); '
        'Write-Output ("SLOWSAID=" + $(if ($slow -match "timed out") { "yes" } else { "no" })); '
        'Write-Output ("ELAPSED=" + [int]((Get-Date) - $t).TotalSeconds); '
        # A missing executable never sets an exit code at all. The job still finishes, so an
        # absent code has to be read as failure or the summary reports a successful install of
        # nothing.
        '$miss = Invoke-NativeTimed -Exe "solai-not-a-command-xyz" -TimeoutSec 60 -Arguments @("x"); '
        'Write-Output ("EXITMISS=" + $script:NativeExit); '
        'Write-Output ("MISSSAID=" + $(if ($miss) { "yes" } else { "no" }))'
    ) % INSTALLER
    code, out = run_ps(probe)

    s.ok('IN-18', 'a timed command that succeeds reports zero and hands back its output',
         field(out, 'EXITOK') == '0' and 'hello' in field(out, 'OUTOK'), out[-300:])
    s.eq('IN-19', "a failing command's own exit code is reported, not the job's state",
         field(out, 'EXIT1602'), '1602')

    elapsed = field(out, 'ELAPSED')
    s.ok('IN-20', 'a command that outruns its deadline is killed, named, and not waited out',
         field(out, 'EXITSLOW') == '-1' and field(out, 'SLOWSAID') == 'yes'
         and elapsed.isdigit() and int(elapsed) < 20,
         'exit %r, named %r, %r seconds against a 3 second deadline over a 30 second command'
         % (field(out, 'EXITSLOW'), field(out, 'SLOWSAID'), elapsed))

    s.ok('IN-21', 'a missing executable is a failure with a reason, not a silent success',
         field(out, 'EXITMISS') not in ('', '0') and field(out, 'MISSSAID') == 'yes',
         'exit %r, explained %r' % (field(out, 'EXITMISS'), field(out, 'MISSSAID')))


def group_network(s):
    """The two guards that exist because of what a managed image does to a download."""
    code, out = run_ps(
        '. "%s" -DryRun *> $null; Write-Output ("TLS=" + $(if (([Net.ServicePointManager]'
        '::SecurityProtocol -band [Net.SecurityProtocolType]::Tls12) -ne 0) {"yes"} else {"no"}))'
        % INSTALLER)
    # A fresh 5.1 process starts on SystemDefault, which reads as 0 here, so this says the
    # script turned TLS 1.2 on rather than that the machine happened to be there already.
    # Without it, an image pinned to 1.0/1.1 fails every download with an SSL/TLS message
    # thrown from inside Invoke-WebRequest, where nothing in this script was catching it.
    s.eq('IN-22', 'TLS 1.2 is on for the process before anything is downloaded',
         field(out, 'TLS'), 'yes')

    # The trap cannot be provoked from outside: it exists for errors this script does not
    # raise on a working machine. Injecting one into a COPY is the only way to watch it work,
    # and the copy is what proves the run continues rather than ending on the spot, which is
    # what `irm | iex` does with an uncaught terminating error.
    body = open(INSTALLER, encoding='utf-8').read()
    anchor = "Write-Stage 'preflight'"
    root = tempfile.mkdtemp(prefix='solai-trap-')
    try:
        copy = os.path.join(root, 'install.ps1')
        with open(copy, 'w', encoding='utf-8', newline='') as fh:
            fh.write(body.replace(anchor, anchor + "\nthrow 'solai-test-boom'", 1))
        code, out = run_ps('& "%s" -DryRun' % copy)
        s.ok('IN-23', 'an unexpected terminating error is reported, with its message',
             'unexpected error' in out and 'solai-test-boom' in out, out[-400:])
        s.ok('IN-24', 'and the rest of the run still happens, instead of the window stopping',
             code == 0 and 'Nothing was written' in out, 'exit %s: %s' % (code, out[-400:]))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def group_onedrive(s):
    """-OneDriveRoot: the answer for a machine carrying one root per work tenant."""
    root = tempfile.mkdtemp(prefix='solai-od-')
    try:
        code, out = run_ps('& "%s" -DryRun -OneDriveRoot "%s"' % (INSTALLER, root))
        s.ok('IN-25', 'an explicit -OneDriveRoot is taken as given, and ranking is skipped',
             ('using -OneDriveRoot: ' + root) in out and 'picked ' not in out, out[:600])
    finally:
        shutil.rmtree(root, ignore_errors=True)

    missing = os.path.join(tempfile.gettempdir(), 'solai-no-such-onedrive-xyz')
    code, out = run_ps('& "%s" -DryRun -OneDriveRoot "%s"' % (INSTALLER, missing))
    # Red text alone would leave stage 6 closing the run with "sign in to OneDrive" on a
    # machine already signed in, when the only thing wrong was the path that was typed.
    s.ok('IN-26', 'a -OneDriveRoot that does not exist becomes an action, not just red text',
         'does not exist' in out and 'action' in out and missing in out, out[:600])


def group_claude_code(s):
    """Stage 2 cannot run here - it installs Claude Code for real - so its order is gated
    statically. The order is the whole change: an ordinary global npm install is not what
    endpoint protection deletes mid-run, and downloading a script to disk to run it is."""
    body = open(INSTALLER, encoding='utf-8').read()
    npm = body.find("Have 'npm'")
    fetch = body.find('https://claude.ai/install.ps1')
    s.ok('IN-27', 'npm is tried before the download-and-run fallback',
         npm != -1 and fetch != -1 and npm < fetch,
         'npm branch at %s, the fetch at %s' % (npm, fetch))

    # The fetch used to fail with one line on screen and nothing in the summary, on the stage
    # whose failure makes every stage after it pointless.
    # Bounded by the `finally` that closes the catch, not by a character count: the branch
    # after it carries a Need of its own, and a window wide enough to include it stays green
    # when the one in the catch is deleted.
    end = body.find('} finally {', fetch) if fetch != -1 else -1
    tail = body[fetch:end] if end != -1 else ''
    s.ok('IN-28', 'a fetch that fails reaches the summary, not only the screen',
         "Say 'failed'" in tail and 'Need (' in tail,
         'the catch around the fallback download, %d characters of it' % len(tail))


GROUPS = (group_shape, group_dry_run, group_bare, group_helpers,
          group_timed, group_network, group_onedrive, group_claude_code)


def printable(text):
    """Text the console can actually take.

    A failure detail can carry PowerShell's own error message, which on a non-English Windows
    is not encodable in the console codepage. That crashed the report where it lists failures
    - the one moment it has to work - and lost every line of it.
    """
    enc = getattr(sys.stdout, 'encoding', None) or 'utf-8'
    return text.encode(enc, 'replace').decode(enc, 'replace')


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
        print(printable(lines))
    print('')
    print('  ' + ('INSTALL GATE GREEN' if suite.green() else 'INSTALL GATE RED'))
    return 0 if suite.green() else 1


if __name__ == '__main__':
    sys.exit(main())
