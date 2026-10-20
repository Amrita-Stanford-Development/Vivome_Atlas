// The Atlas page's upload flow (web/js/atlas/director.js): every rule of the
// state machine, and that it never changes a state in place.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { GUIDED, MAX_ATTEMPTS, initialState, sidebarFor, transition } from '../js/atlas/director.js';

const file = { name: 'cells.tsv', size: 10 };
const check = { ok: true, cells: 238, problems: [] };
const badCheck = { ok: false, cells: 4000, problems: ['too many cells'] };
const response = { cells: [{ cell_id: 'a' }] };
const error = new Error('boom');

// Runs events from a state, checking each step returns a new object and
// leaves the old one as it was.
function run(state, ...events) {
  for (const event of events) {
    const before = JSON.stringify(state);
    const next = transition(state, event);
    assert.equal(JSON.stringify(state), before, `${event.type} changed ${state.name} in place`);
    state = next;
  }
  return state;
}

const chosen = () => run(initialState(), { type: 'FILE_CHOSEN', file }, { type: 'CHECKED', check });
const sending = () => run(chosen(), { type: 'SEND' });
const working = () => run(sending(), { type: 'UPLOADED', since: 1000 });
const interactive = () => run(working(), { type: 'RESPONSE', response }, { type: 'FINISHED' }, { type: 'RECEIPT_DONE' },
  { type: 'FLIGHT_DONE' }, { type: 'SETTLED' });

const ALL = ['idle', 'checking', 'chosen', 'sending', 'working', 'busy', 'finishing', 'receipt', 'flying', 'settling',
  'interactive', 'failed'];
// One example of every state.
function everyState() {
  const busy = run(working(), { type: 'BUSY', retryAfter: 30 });
  const finishing = run(working(), { type: 'RESPONSE', response });
  const receipt = run(finishing, { type: 'FINISHED' });
  const flying = run(receipt, { type: 'RECEIPT_DONE' });
  const settling = run(flying, { type: 'FLIGHT_DONE' });
  const states = {
    idle: initialState(),
    checking: run(initialState(), { type: 'FILE_CHOSEN', file }),
    chosen: chosen(),
    sending: sending(),
    working: working(),
    busy,
    finishing,
    receipt,
    flying,
    settling,
    interactive: interactive(),
    failed: run(working(), { type: 'FAILED', error }),
  };
  assert.deepEqual(Object.values(states).map((s) => s.name), ALL);
  return states;
}

test('it starts idle', () => {
  assert.deepEqual(initialState(), { name: 'idle' });
  assert.notEqual(initialState(), initialState());
  assert.deepEqual([...GUIDED].sort(), ['finishing', 'flying', 'receipt', 'settling']);
  assert.equal(MAX_ATTEMPTS, 3);
});

test('choosing and checking a file', () => {
  const states = everyState();
  for (const name of ['idle', 'chosen', 'failed', 'interactive']) {
    const other = { name: 'other.csv' };
    assert.deepEqual(transition(states[name], { type: 'FILE_CHOSEN', file: other }), { name: 'checking', file: other }, name);
  }
  for (const name of ['checking', 'sending', 'working', 'busy', 'finishing', 'receipt', 'flying', 'settling']) {
    assert.equal(transition(states[name], { type: 'FILE_CHOSEN', file }), states[name], name);
  }
  assert.deepEqual(chosen(), { name: 'chosen', file, check });
  const failed = run(initialState(), { type: 'FILE_CHOSEN', file }, { type: 'CHECK_FAILED', error });
  assert.deepEqual(failed, { name: 'failed', file, error, stage: 'check' });
  assert.equal(transition(failed, { type: 'RETRY' }), failed, 'nothing to send again without a check');
  // A check that comes back for a file no longer chosen is ignored.
  const checking = run(initialState(), { type: 'FILE_CHOSEN', file });
  assert.equal(transition(checking, { type: 'CHECKED', check, file: { name: 'stale' } }), checking);
  assert.equal(transition(states.chosen, { type: 'CHECKED', check }), states.chosen);
});

test('a file is sent only when it passed its check', () => {
  assert.deepEqual(sending(), { name: 'sending', file, check, attempt: 1 });
  const bad = run(initialState(), { type: 'FILE_CHOSEN', file }, { type: 'CHECKED', check: badCheck });
  assert.equal(transition(bad, { type: 'SEND' }), bad);
  assert.deepEqual(working(), { name: 'working', file, check, attempt: 1, since: 1000 });
  assert.deepEqual(run(sending(), { type: 'UPLOADED' }), { name: 'working', file, check, attempt: 1 });
});

test('a busy service is tried again, three times in all', () => {
  let state = run(sending(), { type: 'BUSY', retryAfter: 30 });
  assert.deepEqual(state, { name: 'busy', file, check, attempt: 1, retryAfter: 30 });
  state = run(state, { type: 'RETRY' });
  assert.deepEqual(state, { name: 'sending', file, check, attempt: 2 });
  state = run(state, { type: 'UPLOADED' }, { type: 'BUSY', retryAfter: 12 });
  assert.deepEqual(state, { name: 'busy', file, check, attempt: 2, retryAfter: 12 });
  state = run(state, { type: 'RETRY' });
  assert.equal(state.attempt, 3);
  const busyError = { kind: 'busy' };
  state = run(state, { type: 'BUSY', retryAfter: 30, error: busyError });
  assert.equal(state.name, 'failed');
  assert.equal(state.stage, 'busy');
  assert.equal(state.error, busyError);
  assert.deepEqual([state.file, state.check], [file, check]);
  // Sending again from a failure starts over from the first attempt.
  assert.deepEqual(run(state, { type: 'RETRY' }), { name: 'sending', file, check, attempt: 1 });
});

test('cancelling goes back to the chosen file', () => {
  const states = everyState();
  for (const name of ['sending', 'working', 'busy']) {
    assert.deepEqual(transition(states[name], { type: 'CANCEL' }), { name: 'chosen', file, check }, name);
  }
  for (const name of ['idle', 'chosen', 'finishing', 'interactive', 'failed']) {
    assert.equal(transition(states[name], { type: 'CANCEL' }), states[name], name);
  }
  const example = run(initialState(), { type: 'EXAMPLE' });
  assert.deepEqual(transition(example, { type: 'CANCEL' }), { name: 'idle' }, 'an example with no file chosen');
});

test('the recorded example', () => {
  const states = everyState();
  for (const name of ['idle', 'chosen', 'interactive', 'failed']) {
    const next = transition(states[name], { type: 'EXAMPLE', since: 5 });
    assert.equal(next.name, 'working', name);
    assert.equal(next.example, true);
    assert.equal(next.since, 5);
    assert.equal(next.response, undefined, 'no old answer carried');
  }
  for (const name of ['checking', 'sending', 'working', 'busy', 'finishing', 'receipt', 'flying', 'settling']) {
    assert.equal(transition(states[name], { type: 'EXAMPLE' }), states[name], name);
  }
  const example = run(initialState(), { type: 'EXAMPLE' });
  assert.deepEqual(example, { name: 'working', example: true });
  assert.equal(transition(example, { type: 'BUSY', retryAfter: 30 }), example, 'the example never waits on the service');
  const done = run(example, { type: 'RESPONSE', response }, { type: 'SKIP' });
  assert.deepEqual(done, { name: 'interactive', example: true, response });
  // A chosen file stays chosen through the example.
  const withFile = run(chosen(), { type: 'EXAMPLE' });
  assert.deepEqual(withFile, { name: 'working', file, check, example: true });
  // A failed example runs again.
  const failed = run(example, { type: 'FAILED', error });
  assert.deepEqual(failed, { name: 'failed', file: undefined, check: undefined, error, stage: 'working', example: true });
  assert.deepEqual(run(failed, { type: 'RETRY', since: 9 }), { name: 'working', example: true, since: 9 });
});

test('the guided landing plays through, and SKIP jumps to exploring', () => {
  const steps = [['RESPONSE', 'finishing'], ['FINISHED', 'receipt'], ['RECEIPT_DONE', 'flying'], ['FLIGHT_DONE', 'settling'],
    ['SETTLED', 'interactive']];
  let state = working();
  for (const [type, name] of steps) {
    state = run(state, { type, response });
    assert.deepEqual(state, { name, file, check, response }, type);
  }
  const states = everyState();
  for (const name of ALL) {
    const next = transition(states[name], { type: 'SKIP' });
    if (GUIDED.has(name)) assert.deepEqual(next, { name: 'interactive', file, check, response }, name);
    else assert.equal(next, states[name], name);
  }
  // Each step's event applies only in its own state.
  for (let k = 1; k < steps.length; k += 1) {
    const [type] = steps[k];
    const from = steps[k - 1][1];
    for (const name of ALL) {
      const next = transition(states[name], { type });
      if (name === from) assert.notEqual(next, states[name], `${type} in ${name}`);
      else assert.equal(next, states[name], `${type} in ${name}`);
    }
  }
  assert.equal(transition(states.working, { type: 'RESPONSE' }), states.working, 'a response needs its answer');
  assert.equal(run(sending(), { type: 'RESPONSE', response }).name, 'finishing', 'an answer before the upload event');
});

test('replaying the landing keeps the same answer', () => {
  const state = interactive();
  const replay = transition(state, { type: 'REPLAY' });
  assert.deepEqual(replay, { name: 'receipt', file, check, response });
  assert.equal(replay.response, response);
  const states = everyState();
  for (const name of ALL.filter((n) => n !== 'interactive')) {
    assert.equal(transition(states[name], { type: 'REPLAY' }), states[name], name);
  }
});

test('a failure keeps the file and its check, from any state but idle', () => {
  const states = everyState();
  for (const name of ALL) {
    const next = transition(states[name], { type: 'FAILED', error });
    if (name === 'idle') {
      assert.equal(next, states.idle);
      continue;
    }
    assert.equal(next.name, 'failed', name);
    assert.equal(next.error, error);
    assert.equal(next.stage, name, 'the state it failed in');
    assert.equal(next.file, file);
    assert.equal(next.check, name === 'checking' ? undefined : check);
  }
  assert.equal(transition(states.working, { type: 'FAILED', error, stage: 'upload' }).stage, 'upload');
  assert.deepEqual(transition(states.failed, { type: 'RETRY' }), { name: 'sending', file, check, attempt: 1 });
  const unsendable = { name: 'failed', file, check: badCheck, error, stage: 'working' };
  assert.equal(transition(unsendable, { type: 'RETRY' }), unsendable);
});

test('clearing goes back to idle', () => {
  const states = everyState();
  for (const name of ALL) {
    const next = transition(states[name], { type: 'CLEAR' });
    if (['chosen', 'interactive', 'failed'].includes(name)) assert.deepEqual(next, { name: 'idle' }, name);
    else assert.equal(next, states[name], name);
  }
});

test('an event that does not apply leaves the very same state', () => {
  const states = everyState();
  for (const name of ALL) {
    for (const event of [{ type: 'NOPE' }, {}, null, undefined, { type: 'RETRY' }, { type: 'UPLOADED' }]) {
      const next = transition(states[name], event);
      const applies = (event?.type === 'RETRY' && ['busy', 'failed'].includes(name))
        || (event?.type === 'UPLOADED' && name === 'sending');
      if (!applies) assert.equal(next, states[name], `${name} ${JSON.stringify(event)}`);
      else assert.notEqual(next, states[name]);
    }
  }
});

test('the sidebar folds away while an answer plays, and comes back for the next choice', () => {
  const at = (name, extra = {}) => ({ name, ...extra });
  // Sent: folded, and remembered as folded by the page.
  assert.deepEqual(sidebarFor(at('sending'), { open: true, folded: false }), { open: false, folded: true });
  assert.deepEqual(sidebarFor(at('working', { example: true }), { open: true, folded: false }), { open: false, folded: true });
  // It stays folded through the landing and the answer.
  for (const name of ['working', 'busy', 'finishing', 'receipt', 'flying', 'settling', 'interactive']) {
    assert.deepEqual(sidebarFor(at(name), { open: false, folded: true }), { open: false, folded: true }, name);
  }
  // Cleared, cancelled or failed: back.
  for (const name of ['idle', 'chosen', 'failed']) {
    assert.deepEqual(sidebarFor(at(name), { open: false, folded: true }), { open: true, folded: false }, name);
  }
  // Closed by the visitor before sending: it stays closed afterwards too.
  assert.deepEqual(sidebarFor(at('sending'), { open: false, folded: false }), { open: false, folded: false });
  assert.deepEqual(sidebarFor(at('idle'), { open: false, folded: false }), { open: false, folded: false });
  // Choosing or checking a file leaves it alone.
  assert.deepEqual(sidebarFor(at('checking'), { open: true, folded: false }), { open: true, folded: false });
});

test('new limits replace a chosen file\'s check, and only then', () => {
  const chosen = { name: 'chosen', file: 'f', check: { ok: true, problems: [] } };
  const judged = transition(chosen, { type: 'LIMITS', check: { ok: false, problems: ['too few'] } });
  assert.deepEqual(judged, { name: 'chosen', file: 'f', check: { ok: false, problems: ['too few'] } });
  const sending = { name: 'sending', file: 'f', check: { ok: true } };
  assert.equal(transition(sending, { type: 'LIMITS', check: { ok: false } }), sending);
});

test('limits that change nothing leave the state as it was', () => {
  const file = { name: 'a.csv' };
  const check = { ok: true, problems: [], cells: 40 };
  const chosen = { name: 'chosen', file, check };
  assert.equal(transition(chosen, { type: 'LIMITS', check: { ...check } }), chosen);
  const worse = transition(chosen, { type: 'LIMITS', check: { ...check, ok: false, problems: ['too many cells'] } });
  assert.notEqual(worse, chosen);
  assert.equal(worse.check.ok, false);
});
