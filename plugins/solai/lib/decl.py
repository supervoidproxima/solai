# -*- coding: utf-8 -*-
"""Declarations: the single source of truth for a card class and an archetype.

A card class is declared once, in one TOML file. Five projections are generated from it,
and none of them is authoritative:

    class TOML  ->  _system/data-dictionary.md   (status matrix, enums, schema, links)
                ->  CLAUDE.md card-index region  (routing only; may never name a field)
                ->  .claude/skills/<class>/SKILL.md
                ->  registry.base                (one view)
                ->  validate_cards.py            (reads the TOML at runtime; data, not codegen)

TOML because `tomllib` is stdlib and pyyaml is not installed on the target machine; because
comments are allowed, and a declaration carries rationale that belongs beside the field; and
because `tomllib` is read-only, which makes it structurally impossible for this engine to
quietly rewrite a declaration it was only supposed to read.

Loading FAILS FAST and names the reason. A declaration set that does not hold together is
not partially applied: the projections would disagree, which is the one thing this design
exists to prevent.
"""
import os
import tomllib

FIELD_TYPES = {'scalar', 'enum', 'int', 'bool', 'date', 'list<wl>', 'list<str>'}
LINK_KINDS = {'bidirectional', 'one-way', 'lateral', 'lookup'}
CITE_STYLES = {'footnotes', 'inline-wikilink', 'none'}
GOVERNANCE_TIERS = ('light', 'standard', 'governed')

# How a card of this class is named on disk. `bare-id` makes the filename the identifier;
# `slug` names the file for the thing and carries the identifier in `id`, repeated in
# `aliases` so existing `[[PFX-NNN]]` citations still resolve. It is a per-class policy and
# not a vault-wide one: the reason for choosing `slug` is that a graph view of sixteen nodes
# reading DTY-001 to DTY-016 is useless for the one thing that view is for, and that reason
# applies to the class whose cards are being looked at, not to every class beside it.
FILENAME_POLICIES = {'bare-id', 'slug'}
# `id` is accepted because it is the spelling already written into a shipped vault's
# declaration, in a change record that is immutable. Normalised on load, so everything
# downstream sees one word for one idea (D6).
FILENAME_ALIASES = {'id': 'bare-id'}

# An agent is a declared artefact of an archetype, exactly like a card class: one TOML in,
# one projection out, and nothing in the engine core changes to carry it. These are its
# declared vocabularies.
AGENT_MODELS = {'inherit', 'haiku', 'sonnet', 'opus'}
RETURN_KINDS = {'records', 'verdict', 'edits', 'report'}
RETURN_TYPES = {'scalar', 'int', 'bool', 'enum', 'list<str>', 'list<obj>'}
# Tools that write. A declaration saying `writes = false` that then asks for one of these is
# not a read-only agent, and the refusal is structural rather than a remark in the prose.
WRITING_TOOLS = {'Write', 'Edit', 'NotebookEdit'}
JOB_MIN = 40

# A workflow is the declared resumable job; `loop` is the ordered way of working in a place; and
# `pipeline` means ONLY the concurrency shape below. One word, one idea (D6).
PHASE_SHAPES = {'pipeline', 'barrier'}
GOAL_MIN = 40
BARRIER_MIN = 25


class DeclError(Exception):
    """Carries every reason at once. A loader that reports one error per run is a loader
    the user runs six times."""

    def __init__(self, errors):
        self.errors = errors
        Exception.__init__(self, '\n'.join('  %s' % e for e in errors))


def _read(path):
    with open(path, 'rb') as fh:
        return tomllib.load(fh)


def _read_text(path):
    """The same file as text, newlines normalised. `tomllib` is read-only by design, so a
    manifest that has to be written back out with its comments intact is handled as text.

    The normalisation is not cosmetic: `stamp.file_sha` reads through Python's text mode and
    therefore hashes `\\n`, so text read any other way would hash differently from the same
    file on disk and every generated region would read STALE for no visible reason."""
    with open(path, 'rb') as fh:
        return fh.read().decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')


# --------------------------------------------------------------------------- classes

class Field(object):
    __slots__ = ('name', 'type', 'card', 'required', 'values', 'value_notes', 'meaning',
                 'derived_by', 'source', 'no_default', 'default')

    def __init__(self, d):
        self.name = d.get('name')
        self.type = d.get('type', 'scalar')
        self.card = d.get('card', '0..1')
        self.required = bool(d.get('required', False))
        self.values = d.get('values', [])
        self.value_notes = d.get('value_notes', {})
        self.meaning = d.get('meaning', '')
        self.derived_by = d.get('derived_by')
        self.source = d.get('source')          # e.g. "partition": values injected at setup
        self.no_default = bool(d.get('no_default', False))
        self.default = d.get('default')

    @property
    def is_list(self):
        return self.type.startswith('list<')


class Link(object):
    __slots__ = ('field', 'target', 'card', 'kind', 'reciprocal', 'meaning')

    def __init__(self, d):
        self.field = d.get('field')
        self.target = d.get('target')
        self.card = d.get('card', '0..N')
        self.kind = d.get('kind', 'one-way')
        self.reciprocal = d.get('reciprocal')
        self.meaning = d.get('meaning', '')


class CardClass(object):
    def __init__(self, data, path):
        self.path = path
        self.raw = data
        self.name = data.get('class')
        self.prefix = data.get('prefix')
        self.folder = data.get('folder')
        self.skill = data.get('skill') or self.name
        self.title = data.get('title') or (self.name or '').title()
        self.purpose = data.get('purpose', '')
        self.minted_by = data.get('minted_by') or ('skill:%s' % self.skill)
        self.archive_folder = data.get('archive_folder')
        raw_filename = data.get('filename') or 'bare-id'
        self.filename = FILENAME_ALIASES.get(raw_filename, raw_filename)
        st = data.get('status', {})
        self.lifecycle = st.get('lifecycle', [])
        self.terminal = st.get('terminal', [])
        self.status_default = st.get('default')
        self.status_notes = st.get('notes', {})
        self.status_rules = st.get('rules', {})
        self.fields = [Field(f) for f in data.get('fields', [])]
        self.links = [Link(l) for l in data.get('links', [])]
        body = data.get('body', {})
        self.required_h2 = body.get('required_h2', [])
        self.optional_h2 = body.get('optional_h2', [])
        self.sources_h3 = body.get('sources_h3')
        self.cite_style = body.get('cite_style', 'none')
        view = data.get('view', {})
        self.view_columns = view.get('columns', [])
        self.view_sort = view.get('sort', [])
        # `skill` (scalar) names the command; `[card-skill]` configures it. TOML forbids a
        # key being both, and the two are genuinely different facts.
        cs = data.get('card-skill', {})
        self.skill_modes = cs.get('modes', ['single'])
        self.skill_shared = cs.get('shared', [])
        self.skill_rubrics = cs.get('rubrics', [])
        self.skill_triggers = cs.get('triggers', [])
        self.induces = cs.get('induces', 'none')

    @property
    def statuses(self):
        return list(self.lifecycle) + list(self.terminal)

    def field(self, name):
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def link(self, field_name):
        for l in self.links:
            if l.field == field_name:
                return l
        return None


# Every key a class declaration may carry, at every level. Without this a declaration can
# say `file-name = "slug"` - or `filename = "slug"` before this release - and be accepted and
# read by nothing, which is the silent failure this loader exists to prevent. `[status.notes]`
# is deliberately absent: it is keyed by status value, so its keys cannot be enumerated.
CLASS_KEYS = {'schema', 'class', 'prefix', 'folder', 'skill', 'title', 'purpose',
              'minted_by', 'archive_folder', 'filename', 'status', 'fields', 'links',
              'body', 'view', 'card-skill'}
STATUS_KEYS = {'lifecycle', 'terminal', 'default', 'notes', 'rules'}
STATUS_RULES_KEYS = {'terminal_callout', 'terminal_relaxes_schema'}
BODY_KEYS = {'required_h2', 'optional_h2', 'sources_h3', 'cite_style'}
VIEW_KEYS = {'columns', 'sort'}
VIEW_SORT_KEYS = {'property', 'direction'}
CARD_SKILL_KEYS = {'modes', 'shared', 'rubrics', 'triggers', 'induces'}
FIELD_KEYS = {'name', 'type', 'card', 'required', 'values', 'value_notes', 'meaning',
              'derived_by', 'source', 'no_default', 'default'}
LINK_KEYS = {'field', 'target', 'card', 'kind', 'reciprocal', 'meaning'}


def _validate_class(c, errors):
    where = os.path.basename(c.path)
    status_raw = c.raw.get('status', {})
    view_raw = c.raw.get('view', {})
    _unknown(where, 'the class', c.raw, CLASS_KEYS, errors)
    _unknown(where, '`[status]`', status_raw, STATUS_KEYS, errors)
    _unknown(where, '`[status.rules]`', status_raw.get('rules', {}), STATUS_RULES_KEYS, errors)
    _unknown(where, '`[body]`', c.raw.get('body', {}), BODY_KEYS, errors)
    _unknown(where, '`[view]`', view_raw, VIEW_KEYS, errors)
    for s_ in view_raw.get('sort', []):
        _unknown(where, 'view sort %r' % s_.get('property'), s_, VIEW_SORT_KEYS, errors)
    _unknown(where, '`[card-skill]`', c.raw.get('card-skill', {}), CARD_SKILL_KEYS, errors)
    for f_ in c.raw.get('fields', []):
        _unknown(where, 'field %r' % f_.get('name'), f_, FIELD_KEYS, errors)
    for l_ in c.raw.get('links', []):
        _unknown(where, 'link %r' % l_.get('field'), l_, LINK_KEYS, errors)
    if not c.name:
        errors.append('%s: no `class` key. A declaration without a class name cannot be projected.' % where)
    if not c.prefix:
        errors.append('%s: no `prefix`.' % where)
    elif not (c.prefix.isupper() and c.prefix.isalpha()):
        errors.append('%s: prefix %r must be uppercase letters only.' % (where, c.prefix))
    if not c.folder:
        errors.append('%s: no `folder`.' % where)
    if c.filename not in FILENAME_POLICIES:
        errors.append('%s: filename policy %r is unknown. Known: %s.'
                      % (where, c.raw.get('filename'), ', '.join(sorted(FILENAME_POLICIES))))
    if not c.lifecycle and not c.terminal:
        errors.append('%s: no status values. A class with no lifecycle cannot satisfy D2.' % where)
    if c.status_default and c.status_default not in c.statuses:
        errors.append('%s: default status %r is not in lifecycle or terminal.' % (where, c.status_default))
    for v in c.terminal:
        if v in c.lifecycle:
            errors.append('%s: status %r declared both live and terminal.' % (where, v))
    seen = set()
    for f in c.fields:
        if not f.name:
            errors.append('%s: a field has no name.' % where)
            continue
        if f.name in seen:
            errors.append('%s: field %r declared twice.' % (where, f.name))
        seen.add(f.name)
        if f.type not in FIELD_TYPES:
            errors.append('%s: field %r has unknown type %r. Known: %s'
                          % (where, f.name, f.type, ', '.join(sorted(FIELD_TYPES))))
        if f.type == 'enum' and not f.values and not f.source:
            errors.append('%s: enum field %r declares no values and no source.' % (where, f.name))
        if f.required and f.derived_by:
            errors.append('%s: field %r is both required and derived. A derived field cannot be '
                          'required of the author.' % (where, f.name))
        if '_' in f.name:
            errors.append('%s: field %r uses an underscore. Keys are kebab-case.' % (where, f.name))
    for l in c.links:
        if not l.field or not l.target:
            errors.append('%s: a link declares no field or no target.' % where)
            continue
        if l.field in seen:
            errors.append('%s: %r is declared as both a field and a link.' % (where, l.field))
        seen.add(l.field)
        if l.kind not in LINK_KINDS:
            errors.append('%s: link %r has unknown kind %r. Known: %s'
                          % (where, l.field, l.kind, ', '.join(sorted(LINK_KINDS))))
        if l.kind == 'bidirectional' and not l.reciprocal:
            errors.append('%s: bidirectional link %r names no reciprocal field on %s.'
                          % (where, l.field, l.target))
        if l.kind == 'lateral' and l.target != c.name:
            errors.append('%s: link %r is lateral but targets %r. Lateral means same-class.'
                          % (where, l.field, l.target))
    if c.cite_style not in CITE_STYLES:
        errors.append('%s: cite_style %r unknown. Known: %s'
                      % (where, c.cite_style, ', '.join(sorted(CITE_STYLES))))
    for col in c.view_columns:
        base = col.split('.')[0]
        if base in ('file', 'note'):
            continue
        if col not in seen and col not in ('tags', 'date', 'type', 'id', 'status', 'title'):
            errors.append('%s: view column %r is not a declared field or link.' % (where, col))
    if c.filename == 'slug' and 'id' not in c.view_columns:
        errors.append('%s: filename is `slug` and the view names no `id` column, so the one '
                      'view built for finding a card cannot show its identifier.' % where)


# --------------------------------------------------------------------------- agents

class Return(object):
    """One field of an agent's return schema. The schema is why an agent is checkable."""

    __slots__ = ('name', 'type', 'required', 'values', 'meaning', 'of')

    def __init__(self, d):
        self.name = d.get('name')
        self.type = d.get('type', 'scalar')
        self.required = bool(d.get('required', False))
        self.values = d.get('values', [])
        self.meaning = d.get('meaning', '')
        self.of = d.get('of', [])          # for list<obj>: the keys each object carries


class Eval(object):
    """One thing that must hold about what the agent returned, and what makes it fail.

    `fails_when` is required. An eval with no failure condition is a description of the
    agent's intentions, and a roster of those is exactly the machinery D1 forbids: a
    capability declared with no assertion behind it.
    """

    __slots__ = ('id', 'asserts', 'fails_when', 'note')

    def __init__(self, d):
        self.id = d.get('id')
        self.asserts = d.get('asserts', '')
        self.fails_when = d.get('fails_when')
        self.note = d.get('note', '')


class Agent(object):
    """A declared job with a return schema and evals that can fail it.

    Deliberately NOT a role-play prompt. The declaration says what the agent is sent to do,
    what it must hand back, and what would make the answer wrong. Nothing in it describes a
    persona, because a persona cannot be checked and a return schema can.
    """

    def __init__(self, data, path):
        self.path = path
        self.raw = data
        self.name = data.get('agent')
        self.title = data.get('title') or (self.name or '').replace('-', ' ').title()
        self.job = data.get('job', '')
        self.sent_when = data.get('sent_when', '')
        self.model = data.get('model', 'inherit')
        self.tools = data.get('tools', [])
        self.writes = bool(data.get('writes', False))
        self.induces = data.get('induces', 'none')
        self.reads = data.get('reads', [])
        self.refusals = data.get('refusals', [])
        ret = data.get('returns', {})
        self.return_kind = ret.get('kind', 'report')
        self.return_meaning = ret.get('meaning', '')
        self.returns = [Return(r) for r in ret.get('fields', [])]
        self.evals = [Eval(e) for e in data.get('evals', [])]

    # `folder` and `prefix` exist on a class and not here. An agent mints nothing and owns
    # no path in the vault, which is why it needs neither.

    def field(self, name):
        for r in self.returns:
            if r.name == name:
                return r
        return None


# The declared keys, so a mistyped one is refused rather than ignored. A key that does nothing
# is the same silent failure as a key TOML swallowed under a table header: the author believes
# it took effect, and nothing ever says otherwise.
AGENT_KEYS = {'schema', 'agent', 'title', 'job', 'sent_when', 'model', 'tools', 'writes',
              'induces', 'reads', 'refusals', 'returns', 'evals'}
RETURN_FIELD_KEYS = {'name', 'type', 'required', 'values', 'meaning', 'of'}
RETURNS_KEYS = {'kind', 'meaning', 'fields'}
EVAL_KEYS = {'id', 'asserts', 'fails_when', 'note'}


def _unknown(where, what, data, allowed, errors):
    for key in sorted(set(data) - allowed):
        errors.append('%s: %s carries unknown key %r. It would be read by nothing, so the '
                      'declaration would not mean what it says. Known: %s'
                      % (where, what, key, ', '.join(sorted(allowed))))


def _validate_agent(a, errors):
    where = os.path.basename(a.path)
    _unknown(where, 'the agent', a.raw, AGENT_KEYS, errors)
    _unknown(where, '`[returns]`', a.raw.get('returns', {}), RETURNS_KEYS, errors)
    for r in a.raw.get('returns', {}).get('fields', []):
        _unknown(where, 'return field %r' % r.get('name'), r, RETURN_FIELD_KEYS, errors)
    for e in a.raw.get('evals', []):
        _unknown(where, 'eval %r' % e.get('id'), e, EVAL_KEYS, errors)
    if not a.name:
        errors.append('%s: no `agent` key. A declaration without an agent name cannot be '
                      'projected.' % where)
    elif a.name != a.name.lower() or '_' in a.name or ' ' in a.name:
        errors.append('%s: agent name %r must be lowercase kebab-case, like the skills it '
                      'sits beside.' % (where, a.name))
    if not a.job:
        errors.append('%s: no `job`. An agent with no declared job is a name.' % where)
    elif len(a.job.strip()) < JOB_MIN:
        errors.append('%s: `job` is %d characters. Under %d it names a topic rather than a '
                      'job, and the agent cannot be sent anywhere by it.'
                      % (where, len(a.job.strip()), JOB_MIN))
    if a.model not in AGENT_MODELS:
        errors.append('%s: unknown model %r. Known: %s'
                      % (where, a.model, ', '.join(sorted(AGENT_MODELS))))
    if not a.tools:
        errors.append('%s: no `tools`. An agent that declares no tools cannot do anything, '
                      'and an agent with every tool cannot be reasoned about.' % where)
    if not a.writes:
        bad = sorted(set(a.tools) & WRITING_TOOLS)
        if bad:
            errors.append('%s: declares `writes = false` but asks for %s. Either it writes and '
                          'says so, or it does not and drops the tool.'
                          % (where, ', '.join(bad)))
    if a.return_kind not in RETURN_KINDS:
        errors.append('%s: unknown return kind %r. Known: %s'
                      % (where, a.return_kind, ', '.join(sorted(RETURN_KINDS))))
    if not a.returns:
        errors.append('%s: `[returns]` declares no fields. An agent with no return schema '
                      'hands back prose, and prose is what nothing downstream can check.'
                      % where)
    seen = set()
    for r in a.returns:
        if not r.name:
            errors.append('%s: a return field has no name.' % where)
            continue
        if r.name in seen:
            errors.append('%s: return field %r declared twice.' % (where, r.name))
        seen.add(r.name)
        if r.type not in RETURN_TYPES:
            errors.append('%s: return field %r has unknown type %r. Known: %s'
                          % (where, r.name, r.type, ', '.join(sorted(RETURN_TYPES))))
        if r.type == 'enum' and not r.values:
            errors.append('%s: enum return field %r declares no values.' % (where, r.name))
        if r.type == 'list<obj>' and not r.of:
            errors.append('%s: return field %r is a list of objects but names no keys in `of`. '
                          'A list of unspecified objects is not a schema.' % (where, r.name))
        if '_' in r.name:
            errors.append('%s: return field %r uses an underscore. Keys are kebab-case.'
                          % (where, r.name))
    if not a.evals:
        errors.append('%s: no `[[evals]]`. Nothing may assert what it cannot show (D1), and an '
                      'agent with no eval asserts a capability with nothing behind it.' % where)
    eval_ids = set()
    for e in a.evals:
        if not e.id:
            errors.append('%s: an eval has no `id`.' % where)
        elif e.id in eval_ids:
            errors.append('%s: eval id %r used twice.' % (where, e.id))
        else:
            eval_ids.add(e.id)
        if not e.asserts:
            errors.append('%s: eval %r asserts nothing.' % (where, e.id))
        if not e.fails_when:
            errors.append('%s: eval %r declares no `fails_when`. An eval that cannot fail is a '
                          'description, and a roster of descriptions is the machinery this '
                          'package refuses.' % (where, e.id))


def load_agent(path):
    """Load and validate a single agent in isolation. For `place agent` and for tests."""
    a = Agent(_read(path), path)
    errors = []
    _validate_agent(a, errors)
    if errors:
        raise DeclError(errors)
    return a


# --------------------------------------------------------------------------- workflows

class Phase(object):
    """One stage of a workflow: an agent, a thing to run it over, and a concurrency shape.

    `barrier_because` is required on a barrier and refused on a pipeline. A barrier is the
    expensive choice - every branch waits for the slowest - so the declaration is where it has
    to earn itself, in prose, next to the stage that pays for it.
    """

    __slots__ = ('n', 'title', 'agent', 'shape', 'over', 'detail', 'barrier_because', 'effort',
                 'carry')

    def __init__(self, d):
        self.n = d.get('n')
        self.title = d.get('title')
        self.agent = d.get('agent')
        self.shape = d.get('shape', 'pipeline')
        self.over = d.get('over', '')
        self.detail = d.get('detail', '')
        self.barrier_because = d.get('barrier_because')
        self.effort = d.get('effort')
        # Which of this agent's return fields feeds the next phase. Declared rather than
        # inferred: the alternative is passing whole result objects downstream, which reaches
        # the next agent as "[object Object]" and runs anyway.
        self.carry = d.get('carry')

    @property
    def is_barrier(self):
        return self.shape == 'barrier'


class Workflow(object):
    """A declared multi-stage job, projected as a script rather than described in prose.

    The declaration names the phases and which agent each one calls; the script is the
    projection. Nothing here decides HOW an agent does its job - that is the agent's own
    declaration - so a workflow is a shape and a running order, and nothing else.
    """

    def __init__(self, data, path):
        self.path = path
        self.raw = data
        self.name = data.get('workflow')
        self.title = data.get('title') or (self.name or '').replace('-', ' ').title()
        self.goal = data.get('goal', '')
        self.input = data.get('input', '')
        self.output = data.get('output', '')
        self.run_when = data.get('run_when', '')
        self.phases = [Phase(p) for p in data.get('phases', [])]

    @property
    def agents(self):
        """Distinct agents this workflow calls, in first-appearance order."""
        out = []
        for p in self.phases:
            if p.agent and p.agent not in out:
                out.append(p.agent)
        return out

    def phase(self, title):
        for p in self.phases:
            if p.title == title:
                return p
        return None


WORKFLOW_KEYS = {'schema', 'workflow', 'title', 'goal', 'input', 'output', 'run_when', 'phases'}
PHASE_KEYS = {'n', 'title', 'agent', 'shape', 'over', 'detail', 'barrier_because',
              'effort', 'carry'}


def _validate_workflow(w, errors):
    where = os.path.basename(w.path)
    _unknown(where, 'the workflow', w.raw, WORKFLOW_KEYS, errors)
    for p in w.raw.get('phases', []):
        _unknown(where, 'phase %r' % p.get('title'), p, PHASE_KEYS, errors)

    if not w.name:
        errors.append('%s: no `workflow` key. A declaration without a name cannot be projected.'
                      % where)
    elif w.name != w.name.lower() or '_' in w.name or ' ' in w.name:
        errors.append('%s: workflow name %r must be lowercase kebab-case.' % (where, w.name))
    if not w.goal:
        errors.append('%s: no `goal`. A workflow with no declared goal cannot be judged finished.'
                      % where)
    elif len(w.goal.strip()) < GOAL_MIN:
        errors.append('%s: `goal` is %d characters. Under %d it names a topic rather than a '
                      'finishable job.' % (where, len(w.goal.strip()), GOAL_MIN))
    if not w.input:
        errors.append('%s: no `input`. A workflow that does not say what it is given cannot be '
                      'started by anyone but its author.' % where)
    if not w.output:
        errors.append('%s: no `output`. A job whose result is unnamed cannot be checked against '
                      'its goal.' % where)

    if len(w.phases) < 2:
        errors.append('%s: %d phase(s). A single-phase workflow is one agent call with ceremony '
                      'around it: send the agent directly.' % (where, len(w.phases)))
    titles, numbers = set(), []
    for i, p in enumerate(w.phases, 1):
        if not p.title:
            errors.append('%s: phase %d has no title.' % (where, i))
            continue
        if p.title in titles:
            errors.append('%s: two phases titled %r. The title is the progress group, so a '
                          'duplicate merges two stages in the report.' % (where, p.title))
        titles.add(p.title)
        numbers.append(p.n)
        if not p.agent:
            errors.append('%s: phase %r names no agent. Every phase is an agent call; a stage '
                          'that is not one belongs in the loop, not in a workflow.'
                          % (where, p.title))
        if p.shape not in PHASE_SHAPES:
            errors.append('%s: phase %r has unknown shape %r. Known: %s'
                          % (where, p.title, p.shape, ', '.join(sorted(PHASE_SHAPES))))
        if not p.over:
            errors.append('%s: phase %r does not say what it runs `over`. Without it the '
                          'projection cannot know what to iterate.' % (where, p.title))
        if p.is_barrier and not p.barrier_because:
            errors.append('%s: phase %r is a barrier and gives no `barrier_because`. A barrier '
                          'makes every branch wait for the slowest, so it justifies itself in '
                          'the declaration or it is a pipeline.' % (where, p.title))
        elif p.is_barrier and len(p.barrier_because.strip()) < BARRIER_MIN:
            errors.append('%s: phase %r justifies its barrier in %d characters. Under %d is a '
                          'restatement, not a reason.'
                          % (where, p.title, len(p.barrier_because.strip()), BARRIER_MIN))
        if not p.is_barrier and p.barrier_because:
            errors.append('%s: phase %r is a pipeline but carries `barrier_because`. The key '
                          'would be read by nothing, so the shape and the prose disagree.'
                          % (where, p.title))
    if numbers and [n for n in numbers if n is not None] != list(
            range(1, len([n for n in numbers if n is not None]) + 1)):
        errors.append('%s: phase numbers are %s. They order the projection, so they run 1..N '
                      'with no gaps.' % (where, numbers))
    for i, p in enumerate(w.phases):
        last = (i == len(w.phases) - 1)
        if p.carry and last:
            errors.append('%s: the last phase %r declares `carry`, but nothing consumes it. The '
                          'workflow returns its result; a carry off the end is a key read by '
                          'nothing.' % (where, p.title))
        if not p.carry and not last:
            errors.append('%s: phase %r does not declare what it carries to the next phase. '
                          'Without it the next stage receives whole result objects, reaches its '
                          'agent as "[object Object]", and runs anyway.' % (where, p.title))

    if w.phases and all(p.is_barrier for p in w.phases if p.title):
        errors.append('%s: every phase is a barrier. That is a sequence of blocking steps, and '
                      'the default is a pipeline: name the one stage that genuinely needs the '
                      'whole prior set.' % where)


def load_workflow(path):
    """Load and validate a single workflow in isolation. For `place workflow` and for tests."""
    w = Workflow(_read(path), path)
    errors = []
    _validate_workflow(w, errors)
    if errors:
        raise DeclError(errors)
    return w


# --------------------------------------------------------------------------- archetype

class Archetype(object):
    def __init__(self, data, root):
        self.root = root
        self.raw = data
        self.name = data.get('archetype')
        self.title = data.get('title', '')
        self.summary = data.get('summary', '')
        self.schema = data.get('schema', 1)
        interview = data.get('interview', {})
        self.asks = interview.get('asks', [])
        self.defaults = interview.get('defaults', {})
        self.partition = interview.get('partition', {})
        self.ids = data.get('ids', {})
        self.class_names = data.get('classes', [])
        self.lookup_names = data.get('lookups', [])
        self.agent_names = data.get('agents', [])
        self.workflow_names = data.get('workflows', [])
        self.folders = data.get('folders', [])
        # Where documents handed in at setup are dropped. Declared so that an archetype can
        # move it; `_inbox` by default because that folder already means unprocessed capture
        # and already has an end state - empty.
        self.materials = data.get('materials', '_inbox')
        self.artefacts = data.get('artefacts', [])
        self.loop = data.get('loop', [])
        self.default_tier = self.defaults.get('governance_tier', 'light')
        self.classes = []
        self.lookups = []
        self.agents = []
        self.workflows = []
        # Set by `load_merged` and by nothing else. `kept` names the declarations this
        # archetype does not carry and the vault being upgraded does, so the plan table can
        # say which rows are present because the vault already had them. `manifest_text` is
        # the compiled manifest body the engine should write, which under a merge is not the
        # package file byte for byte: it has to list the kept names or the next compiled
        # load reads them as strays and reorders every generated index around them.
        self.kept = []
        self.manifest_text = None

    def agent(self, name):
        for a in self.agents:
            if a.name == name:
                return a
        return None

    def workflow(self, name):
        for w in self.workflows:
            if w.name == name:
                return w
        return None

    def artefact(self, aid):
        for a in self.artefacts:
            if a.get('id') == aid:
                return a
        return None


def load_archetype(pkg_root, name):
    """Load an archetype and every class it declares. Raises DeclError with every reason."""
    root = os.path.join(pkg_root, 'archetypes', name)
    manifest = os.path.join(root, 'manifest.toml')
    if not os.path.exists(manifest):
        raise DeclError(['no archetype %r at %s' % (name, manifest)])
    data = _read(manifest)
    arch = Archetype(data, root)
    errors = []

    # TOML nests a bare key under whatever table header precedes it, so `classes = [...]`
    # written below `[ids]` silently becomes `ids.classes` and the archetype loads with
    # nothing in it. Silent is the problem: name it.
    for stray in ('classes', 'lookups', 'agents', 'workflows', 'archetype', 'schema'):
        for tbl in ('ids', 'interview'):
            if isinstance(data.get(tbl), dict) and stray in data[tbl]:
                errors.append('manifest.toml: `%s` is nested under `[%s]`. Top-level keys must '
                              'precede the first table header, or TOML swallows them.'
                              % (stray, tbl))
    # `[[pipeline]]` was renamed to `[[loop]]`. A manifest still using the old key would
    # load with an empty loop and render an empty section, which is the silent failure this
    # loader exists to prevent. Name it instead.
    if 'pipeline' in data:
        errors.append('manifest.toml: `[[pipeline]]` was renamed to `[[loop]]`. The old key is '
                      'read by nothing, so the loop section would render empty.')

    if not arch.class_names and not arch.lookup_names and arch.artefact('card-skills'):
        errors.append('manifest.toml: declares a card-skills artefact but no classes. '
                      'Nothing would be generated.')

    if arch.name != name:
        errors.append('manifest.toml declares archetype %r but lives in %s/' % (arch.name, name))
    if arch.default_tier not in GOVERNANCE_TIERS:
        errors.append('unknown default tier %r' % arch.default_tier)

    # One loop over three declaration kinds. Agents resolve through the same
    # archetype-then-common fallback the lookups already use, which is why "one shared roster,
    # per-archetype selection" needed no new machinery: a manifest lists the agents it takes and
    # the files live once in `common/agents/`.
    for kind, names, bucket, make, check in (
            ('classes', arch.class_names, arch.classes, CardClass, _validate_class),
            ('lookups', arch.lookup_names, arch.lookups, CardClass, _validate_class),
            ('agents', arch.agent_names, arch.agents, Agent, _validate_agent),
            ('workflows', arch.workflow_names, arch.workflows, Workflow, _validate_workflow)):
        for cname in names:
            p = os.path.join(root, kind, '%s.toml' % cname)
            if not os.path.exists(p):
                p_common = os.path.join(pkg_root, 'common', kind, '%s.toml' % cname)
                p = p_common if os.path.exists(p_common) else p
            if not os.path.exists(p):
                errors.append('%s lists %r but %s does not exist.' % (kind, cname, p))
                continue
            try:
                c = make(_read(p), p)
            except tomllib.TOMLDecodeError as exc:
                errors.append('%s: not valid TOML: %s' % (p, exc))
                continue
            check(c, errors)
            bucket.append(c)

    _validate_set(arch, errors)
    if errors:
        raise DeclError(errors)
    return arch


def _discover(os_dir, kind, make, check, listed, errors, notes):
    """Every declaration of one kind, found by listing the directory it lives in.

    `listed` is what the manifest says about this kind, or None where there is no manifest.
    None is not the empty list: comparing against a list that does not exist would report
    every declaration in the vault as an addition.
    """
    d = os.path.join(os_dir, kind)
    found = {}
    for name in sorted(os.listdir(d)) if os.path.isdir(d) else ():
        if not name.endswith('.toml'):
            continue
        p = os.path.join(d, name)
        try:
            obj = make(_read(p), p)
        except tomllib.TOMLDecodeError as exc:
            errors.append('%s: not valid TOML: %s' % (p, exc))
            continue
        key = getattr(obj, 'name', None)
        if not key:
            errors.append('%s: declares no name, so nothing can be projected from it.' % p)
            continue
        check(obj, errors)
        found[key] = obj
    if listed is None:
        return found
    for gone in [n for n in listed if n not in found]:
        notes.append('%s: the manifest lists %r and no declaration is compiled in. Read '
                     'as retired.' % (kind, gone))
    for extra in [n for n in found if n not in listed]:
        notes.append('%s: %r is compiled in and the manifest does not list it. Read as '
                     'added.' % (kind, extra))
    return found


class _Declared(object):
    """The vault side of a merge, for a vault that predates the compiled manifest.

    Only the attributes `load_merged` reads. It is deliberately not an `Archetype`: with no
    manifest there is no title, no tier and no statement of which declarations are lookups,
    and inventing any of those would be this defect in reverse.
    """

    def __init__(self, classes, agents, workflows):
        self.classes = classes
        self.lookups = []
        self.agents = agents
        self.workflows = workflows
        self.lookup_names = ()


def _declared(vault_root):
    """What a vault declares, read off its directories rather than off a manifest.

    -> (declared, notes, errors), where `declared` is None when there is genuinely nothing.

    A missing `manifest.toml` says the vault was built before the engine compiled one in. It
    does NOT say the vault declares nothing, and reading it that way dropped both classes of
    the one vault old enough to need an upgrade: `GAP-007` of the Solai vault, found by
    running a real migration plan and reading the line `0 declared only by this vault`.

    The distinction this turns on is between nothing declared and nothing RECORDED about
    what was declared. A first build is the first: no `_system/os/`, or one with no
    declaration in it, and the package archetype whole is the right answer. Anything else is
    the second.

    Which declarations are lookups cannot be recovered here, because the manifest is the
    only place it is written down. A kept declaration therefore arrives as a class, and the
    note names it, so the one case this cannot get right is visible rather than silent.
    """
    os_dir = os.path.join(vault_root, '_system', 'os')
    if not os.path.isdir(os_dir):
        return None, [], []
    errors, notes = [], []
    cards = _discover(os_dir, 'classes', CardClass, _validate_class, None, errors, notes)
    agents = _discover(os_dir, 'agents', Agent, _validate_agent, None, errors, notes)
    flows = _discover(os_dir, 'workflows', Workflow, _validate_workflow, None, errors, notes)
    if not (cards or agents or flows):
        return None, [], []
    return (_Declared([cards[n] for n in sorted(cards)],
                      [agents[n] for n in sorted(agents)],
                      [flows[n] for n in sorted(flows)]), notes, errors)


def _compiled(vault_root):
    """A vault's own declarations, read and each one validated, but NOT checked as a set.

    -> (archetype, notes, errors). The set check is the caller's because the two callers
    check DIFFERENT sets: `load_compiled` validates the vault's declarations as the whole
    they are, and `load_merged` validates the merged set, where a link this vault's copy
    makes is satisfied by the package's class. Running the set check here would refuse an
    upgrade on account of a state the upgrade resolves.

    WHY THIS EXISTS. `validate_cards.py` has always read `_system/os/classes/*.toml` at
    runtime, so a vault that renames a class is still validated correctly. The emitters read
    the package archetype, so the same vault could never be REGENERATED correctly: its
    `CLAUDE.md` went on naming a class it had retired, and `CLAUDE.md` itself said not to
    hand-edit the block but to edit the declaration - which lived with the generator, in a
    directory the vault's own governance puts out of scope. One real vault gave up and wrote
    a hand-maintained section titled "Where the generated sections are wrong".

    CLASSES ARE DISCOVERED BY LISTING THE DIRECTORY, never from the manifest's `classes`
    list. This is the load-bearing choice. Deleting `decision.toml` IS the retirement and
    adding `duty.toml` IS the rename; reading the list instead would make a stale list
    authoritative and rebuild the whole defect. The manifest's lists are kept only to say
    which declarations are lookups, and to report what changed.

    A name listed with no file, or a file present and unlisted, is a NOTE and never an
    error. Refusing there would block exactly the evolution this exists to permit.
    """
    os_dir = os.path.join(vault_root, '_system', 'os')
    manifest = os.path.join(os_dir, 'manifest.toml')
    if not os.path.exists(manifest):
        raise DeclError(['no compiled manifest at %s. This vault was built before the engine '
                         'compiled one in; the scaffold synthesises it on the next apply.'
                         % manifest])
    arch = Archetype(_read(manifest), os_dir)
    errors, notes = [], []

    def discover(kind, make, check, listed):
        return _discover(os_dir, kind, make, check, listed, errors, notes)

    def ordered(found, listed):
        """Manifest order first, then anything discovered beside it, alphabetically.

        Order is not cosmetic: the emitters walk this list, so it sets the row order of the
        card index, the sections of the data dictionary and the views in the base. Sorting
        by filename instead would rewrite all three on the first compiled run of every
        vault already built, for no reason a reader could see.
        """
        out = [found[n] for n in listed if n in found]
        return out + [found[n] for n in sorted(found) if n not in listed]

    cards = discover('classes', CardClass, _validate_class,
                     list(arch.class_names) + list(arch.lookup_names))
    for c in ordered(cards, list(arch.class_names) + list(arch.lookup_names)):
        (arch.lookups if c.name in arch.lookup_names else arch.classes).append(c)
    arch.agents = ordered(discover('agents', Agent, _validate_agent, arch.agent_names),
                          arch.agent_names)
    arch.workflows = ordered(discover('workflows', Workflow, _validate_workflow,
                                      arch.workflow_names), arch.workflow_names)
    return arch, notes, errors


def load_compiled(vault_root):
    """Load an archetype from a vault's OWN compiled declarations, not from the package.

    -> (archetype, notes). Raises DeclError with every reason, like `load_archetype`.
    The reading and the reasoning are in `_compiled`; this adds the set check.
    """
    arch, notes, errors = _compiled(vault_root)
    _validate_set(arch, errors)
    if errors:
        raise DeclError(errors)
    return arch, notes


def _relist(body, key, names):
    """Rewrite the single top-level `key = [...]` line of a manifest, comments intact.

    Returns the new body, or raises DeclError naming what it could not find. It refuses
    rather than guessing: a manifest whose class list silently failed to update is the
    stale-list defect `load_compiled` was written to end, arriving by another door.
    """
    out, hits = [], []
    for i, line in enumerate(body.split('\n')):
        head, eq, rest = line.partition('=')
        if not eq or head.strip() != key or head[:1].isspace():
            out.append(line)
            continue
        if rest.count('[') != 1 or ']' not in rest:
            raise DeclError(['manifest.toml line %d: `%s` is not a single-line array, so the '
                             'merged list cannot be written back without guessing at the '
                             'shape. Put the array on one line.' % (i + 1, key)])
        hits.append(i)
        out.append('%s= [%s]' % (head, ', '.join('"%s"' % n for n in names)))
    if len(hits) != 1:
        raise DeclError(['manifest.toml: expected exactly one top-level `%s = [...]` line and '
                         'found %d. The merged declaration set cannot be recorded.'
                         % (key, len(hits))])
    return '\n'.join(out)


def _covered(folder, declared):
    """Is `folder` the same as, or inside, one of `declared`?

    The same test `_validate_set` applies. Two spellings of one rule is how a merge comes to
    add a folder the validator then rejects, or skip one it then demands.
    """
    return any(folder == d or folder.startswith(d.rstrip('/') + '/')
               for d in declared if d)


def _add_folders(body, entries):
    """Write `[[folders]]` blocks into a manifest's text, after the last one already there.

    Appending at the end of the file would be valid TOML and would read as an afterthought
    in a file a person opens. Inserted here, the folder table stays one block, which is what
    `CLAUDE.md`'s structure section is rendered from.
    """
    if not entries:
        return body
    block = ''.join('[[folders]]\npath = "%s"\npurpose = "%s"\n'
                    % (e['path'], (e.get('purpose') or '').replace('"', "'"))
                    for e in entries)
    at = body.rfind('[[folders]]')
    if at < 0:
        return body.rstrip('\n') + '\n\n' + block
    nxt = body.find('\n[', at + 1)
    while nxt >= 0 and body[nxt + 1:].startswith('[[folders]]'):
        nxt = body.find('\n[', nxt + 1)
    if nxt < 0:
        return body.rstrip('\n') + '\n' + block
    return body[:nxt + 1] + block + body[nxt + 1:]


def load_merged(pkg_root, vault_root, name):
    """Upgrade load: the package archetype, PLUS what this vault declares and it does not.

    -> (archetype, notes). Raises DeclError with every reason, like its two siblings.

    WHY THIS EXISTS. `--from-package` re-imported the archetype whole, which is right for
    artefacts and runtime and wrong for declarations. A class declared in one vault and
    deliberately not written back into the archetype - this vault's `deliverable`, the
    counselor's `platform` and `subject` - vanished on upgrade, taking its folder, its
    skill, its view and its row in every generated index with it. An upgrade that deletes a
    class the vault is using is not an upgrade, and D19 says nothing is deleted by a script.

    THE THREE CASES, applied to classes, lookups, agents and workflows alike. Only the third
    is a judgement:

      package only  -> taken. This is what upgrading means.
      vault only    -> KEPT. Nobody asked for it to go, and the vault is using it.
      both          -> the PACKAGE wins, and the note says so by name, because an upgrade
                       whose declarations lose to the copy already on disk upgrades nothing.
                       A vault that wants to keep its own version of a declaration the package
                       has since adopted renames it first; that is what `class rename` is for.

    ALL FOUR KINDS, not just classes. The first release of this loader guarded classes and
    named agents and workflows as uncovered, on the reasoning that no vault declared one of
    its own. That is an argument about today's vaults and not about the rule: an agent is
    compiled into `_system/os/agents/` exactly as a class is, `load_compiled` discovers it by
    listing the directory exactly as it discovers a class, and a vault that writes one has
    done nothing the engine tells it not to. The failure would have been identical and the
    excuse would have been worse for having been written down.

    A VAULT WITH NO COMPILED MANIFEST still declares what is in its directories. The first
    release of this loader read a missing manifest as "nothing to merge with" and handed back
    the package archetype whole, which is correct for a first build and is a deletion for
    every vault built before the manifest existed - which is precisely the set of vaults an
    upgrade is for. `_declared` covers that case by listing the same directories `_compiled`
    lists, and the first build is told apart by there being no declaration at all rather than
    by the absence of a file that records them.

    KEEPING A DECLARATION IS NOT KEEPING WHAT IT NEEDS, and each release found one more thing
    in the second category: classes, then lookups, agents and workflows, then the FOLDER a kept
    class lives in. `_validate_set` requires every class to sit under a declared folder, and a
    class the package never heard of sits where the vault put it, so the merge kept the class
    and then refused the set it had built. A carried folder is written into the merged manifest
    as well as into this run.

    A kept declaration keeps its OWN path, inside `_system/os/`, so the engine plans a write
    of the file over itself and the row reads NOOP. The merged manifest is rendered here
    rather than copied, because the package manifest does not list the kept names and a
    compiled manifest that does not list what is beside it is the drift this loader reports.
    """
    pkg = load_archetype(pkg_root, name)
    compiled = os.path.join(vault_root, '_system', 'os', 'manifest.toml')
    if os.path.exists(compiled):
        local, notes, errors = _compiled(vault_root)
    else:
        # No manifest is TWO different states and this once treated them as one: a first
        # build, where nothing is declared, and a vault older than the compiled manifest,
        # where plenty is declared and nothing records it. Returning the package archetype
        # whole is right for the first and deletes a class in the second.
        local, notes, errors = _declared(vault_root)
        if local is None:
            return pkg, notes
    if errors:
        raise DeclError(errors)

    lists = {'classes': list(pkg.class_names), 'lookups': list(pkg.lookup_names),
             'agents': list(pkg.agent_names), 'workflows': list(pkg.workflow_names)}
    widened = set()

    def consider(kind, mine, theirs, take):
        """`mine` from the vault, `theirs` the package declarations of the same kind."""
        have = dict((d.name, d) for d in theirs)
        for d in mine:
            if d.name in have:
                # Reported only where the two files actually differ. A note on all five of
                # an unchanged set buries the one row that matters, and "is overwritten" is
                # not true of a byte-identical file: the engine plans that row as a NOOP.
                if _read_text(d.path) != _read_text(have[d.name].path):
                    notes.append('%s: %r is declared by both and the two differ. The package '
                                 "declaration wins; this vault's copy is overwritten."
                                 % (kind, d.name))
                continue
            listed = take(d)
            lists[listed].append(d.name)
            widened.add(listed)
            pkg.kept.append(d.name)
            notes.append('%s: %r is declared by this vault and not by the %s archetype. '
                         'Kept.' % (kind, d.name, name))

    kept_cards = []

    def take_card(d):
        """A lookup on this vault's side stays a lookup: which list a declaration belongs to
        is the vault's statement about it, and the package has no opinion about a name it
        does not carry."""
        kept_cards.append(d)
        if d.name in local.lookup_names:
            pkg.lookups.append(d)
            return 'lookups'
        pkg.classes.append(d)
        return 'classes'

    consider('classes', local.classes + local.lookups, pkg.classes + pkg.lookups, take_card)
    consider('agents', local.agents, pkg.agents,
             lambda d: (pkg.agents.append(d), 'agents')[1])
    consider('workflows', local.workflows, pkg.workflows,
             lambda d: (pkg.workflows.append(d), 'workflows')[1])

    # A kept class needs the folder it lives IN, which the package manifest was never going
    # to declare: a class the package has not heard of lives somewhere the package has not
    # heard of. Keeping the declaration and refusing its folder is how this merge managed to
    # keep a class and then reject the set it had just built. The folder takes the class's own
    # purpose, because it exists to hold that class and no other sentence describes it better.
    carried = []
    for d in kept_cards:
        if not d.folder:
            continue
        if _covered(d.folder, [f.get('path') for f in pkg.folders]):
            continue
        entry = {'path': d.folder, 'purpose': getattr(d, 'purpose', '') or
                 'declared by this vault, for its %r class' % d.name}
        pkg.folders.append(entry)
        carried.append(entry)
        notes.append('folders: %r is declared too, because %r lives there and no folder in '
                     'the %s archetype covers it.' % (d.folder, d.name, name))

    if pkg.kept:
        # Only the lists that gained a name are rewritten. Relisting the rest would be a
        # no-op on today's manifests and a refusal on the first one that writes an array
        # over two lines for a key this merge never had to touch.
        body = _read_text(os.path.join(pkg.root, 'manifest.toml'))
        for key in ('classes', 'lookups', 'agents', 'workflows'):
            if key in widened:
                body = _relist(body, key, lists[key])
        # Into the text as well as into this run: a folder declared only in memory is a
        # folder the NEXT plain run does not know about, and the set check would refuse the
        # vault for a state this merge created.
        body = _add_folders(body, carried)
        pkg.manifest_text = body
        pkg.class_names, pkg.lookup_names = lists['classes'], lists['lookups']
        pkg.agent_names, pkg.workflow_names = lists['agents'], lists['workflows']

    errors = []
    _validate_set(pkg, errors)
    if errors:
        raise DeclError(errors)
    return pkg, notes


def _validate_set(arch, errors):
    """Cross-declaration checks. These are the ones that make the projections consistent."""
    all_decls = arch.classes + arch.lookups
    by_name = {c.name: c for c in all_decls}

    prefixes = {}
    for c in all_decls:
        if not c.prefix:
            continue
        if c.prefix in prefixes:
            errors.append('prefix %s claimed by both %r and %r. One prefix, one minter (D6).'
                          % (c.prefix, prefixes[c.prefix], c.name))
        prefixes[c.prefix] = c.name

    folders = {}
    for c in all_decls:
        if not c.folder:
            continue
        if c.folder in folders:
            errors.append('folder %s claimed by both %r and %r. Ownership of a path must be '
                          'decidable (D4).' % (c.folder, folders[c.folder], c.name))
        folders[c.folder] = c.name

    declared_folders = [f.get('path') for f in arch.folders]
    for c in all_decls:
        if not c.folder:
            continue
        if not any(c.folder == d or c.folder.startswith(d.rstrip('/') + '/')
                   for d in declared_folders if d):
            errors.append('class %r lives in %s, which is under no folder the manifest declares.'
                          % (c.name, c.folder))

    for c in all_decls:
        for l in c.links:
            if l.target not in by_name:
                errors.append('%s.%s targets %r, which is not a declared class or lookup.'
                              % (c.name, l.field, l.target))
                continue
            if l.kind == 'bidirectional':
                other = by_name[l.target]
                back = other.link(l.reciprocal)
                if back is None:
                    errors.append('%s.%s is bidirectional and names reciprocal %r on %s, but %s '
                                  'declares no such link. Edges are authored once and both '
                                  'directions read one table (D3).'
                                  % (c.name, l.field, l.reciprocal, l.target, l.target))
                elif back.target != c.name:
                    errors.append('%s.%s expects %s.%s to point back at %s, but it points at %s.'
                                  % (c.name, l.field, l.target, l.reciprocal, c.name, back.target))
    agent_names, skill_names = {}, {c.skill: c.name for c in arch.classes}
    for a in arch.agents:
        if not a.name:
            continue
        if a.name in agent_names:
            errors.append('agent %s declared twice. One name, one job.' % a.name)
        agent_names[a.name] = a
        if a.name in skill_names:
            errors.append('agent %r has the name of the card skill /%s. Two addressable things '
                          'with one name is the drift D6 forbids.' % (a.name, a.name))

    wf_names = {}
    for w in arch.workflows:
        if not w.name:
            continue
        if w.name in wf_names:
            errors.append('workflow %s declared twice. One name, one job.' % w.name)
        wf_names[w.name] = w
        if w.name in agent_names:
            errors.append('workflow %r has the name of an agent. Two addressable things with '
                          'one name is the drift D6 forbids.' % w.name)
        if w.name in skill_names:
            errors.append('workflow %r has the name of the card skill /%s.' % (w.name, w.name))
        # A workflow may only call agents this archetype actually takes. Otherwise the projected
        # script names a subagent that does not exist in the place, and the failure arrives at
        # run time in a session rather than at load time here.
        for p in w.phases:
            if p.carry and p.agent in agent_names:
                a = agent_names[p.agent]
                f = a.field(p.carry)
                if f is None:
                    errors.append('workflow %s phase %r carries %r, which agent %s does not '
                                  'return. Returns: %s'
                                  % (w.name, p.title, p.carry, p.agent,
                                     ', '.join(r.name for r in a.returns)))
                elif not f.type.startswith('list<'):
                    errors.append('workflow %s phase %r carries %r, which is a %s rather than a '
                                  'list. The next phase iterates the carry, so it has to be one.'
                                  % (w.name, p.title, p.carry, f.type))
            if p.agent and p.agent not in agent_names:
                errors.append('workflow %s phase %r calls agent %r, which this archetype does '
                              'not declare. Declared: %s'
                              % (w.name, p.title, p.agent,
                                 ', '.join(sorted(agent_names)) or 'none'))

    styles = {c.cite_style for c in arch.classes if c.cite_style != 'none'}
    if len(styles) > 1:
        errors.append('classes disagree on cite_style (%s). One vault, one citation convention.'
                      % ', '.join(sorted(styles)))


def load_class(path):
    """Load and validate a single class in isolation. For `place class` and for tests."""
    c = CardClass(_read(path), path)
    errors = []
    _validate_class(c, errors)
    if errors:
        raise DeclError(errors)
    return c
