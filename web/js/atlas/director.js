// The Atlas page's upload flow as one state machine: choosing and checking a
// file, sending it, waiting (and waiting again when the service is busy),
// the guided landing of the answer, and exploring it. Pure: transition()
// returns a new state for an event that applies and the same object for one
// that does not, so the page redraws only on a real change. No clock: an
// event that starts a wait carries its own `since`.

// The states the guided landing plays through; SKIP jumps from any of them
// to exploring.
export const GUIDED = new Set(['finishing', 'receipt', 'flying', 'settling']);

// A busy service is tried this many times in all before the page gives up.
export const MAX_ATTEMPTS = 3;

export const initialState = () => ({ name: 'idle' });

// One short sentence for screen readers, said when the flow moves to another
// step. The status card is not read out: while it waits it changes every
// second (its clock, the send share). A failure's sentence is its
// explanation, which the page supplies; once answered, the number of cells.
export function statusLine(state, { cells = null, failure = '' } = {}) {
  switch (state?.name) {
    case 'checking': return 'Checking the file in your browser.';
    case 'chosen': return state.check?.ok ? 'Checked in your browser; nothing has been sent yet.' : '';
    case 'sending': return 'Sending your file.';
    case 'working': return state.example ? 'Replaying the recorded example; no file is sent.' : 'Waiting for the answer from the service.';
    case 'busy': return 'The service is busy with another file; trying again shortly.';
    case 'failed': return failure;
    case 'finishing': case 'receipt': case 'flying': case 'settling': case 'interactive':
      return cells === null ? '' : `Answers for ${cells.toLocaleString('en-US')} cells are on the map.`;
    default: return '';
  }
}

// The sidebar for a state: it folds away when a file is sent or the example
// starts, so the map has the room, and comes back when the visitor is
// choosing again (cleared, cancelled, failed), unless they moved it
// themselves in between (`folded` is then false).
export function sidebarFor(state, { open, folded }) {
  const name = state?.name;
  if ((name === 'sending' || (name === 'working' && state.example)) && open) return { open: false, folded: true };
  if (folded && ['idle', 'chosen', 'failed'].includes(name)) return { open: true, folded: false };
  return { open, folded };
}

// What a state keeps from the one before it: the file and its check, the
// answer, and whether it is the recorded example.
function carry(state, name, extra = {}) {
  const out = { name };
  if (state.file !== undefined) out.file = state.file;
  if (state.check !== undefined) out.check = state.check;
  if (state.example) out.example = true;
  if (state.response !== undefined && extra.response === undefined) out.response = state.response;
  return Object.assign(out, extra);
}

const canSend = (state) => Boolean(state.file) && state.check?.ok === true;
const since = (event) => (event.since === undefined ? {} : { since: event.since });

export function transition(state, event) {
  if (!state) return initialState();
  if (!event || typeof event.type !== 'string') return state;
  const { name } = state;
  switch (event.type) {
    case 'FILE_CHOSEN':
      if (!['idle', 'chosen', 'failed', 'interactive'].includes(name) || !event.file) return state;
      return { name: 'checking', file: event.file };

    case 'CHECKED':
      // A check of a file no longer chosen is stale.
      if (name !== 'checking' || (event.file !== undefined && event.file !== state.file)) return state;
      return { name: 'chosen', file: state.file, check: event.check };

    case 'LIMITS': {
      // The service's limits arrived or changed after the file was checked;
      // a verdict that did not change leaves the state as it was.
      if (name !== 'chosen' || !event.check) return state;
      const same = state.check?.ok === event.check.ok
        && JSON.stringify(state.check?.problems ?? []) === JSON.stringify(event.check.problems ?? []);
      return same ? state : { name: 'chosen', file: state.file, check: event.check };
    }

    case 'CHECK_FAILED':
      if (name !== 'checking' || (event.file !== undefined && event.file !== state.file)) return state;
      return { name: 'failed', file: state.file, error: event.error, stage: 'check' };

    case 'SEND':
      if (name !== 'chosen' || !canSend(state)) return state;
      return { name: 'sending', file: state.file, check: state.check, attempt: 1 };

    case 'UPLOADED':
      if (name !== 'sending') return state;
      return carry(state, 'working', { attempt: state.attempt, ...since(event) });

    case 'BUSY': {
      if (!(name === 'sending' || name === 'working') || state.example) return state;
      const attempt = state.attempt ?? 1;
      if (attempt >= MAX_ATTEMPTS) {
        return carry(state, 'failed', { error: event.error ?? null, stage: 'busy', attempt });
      }
      return carry(state, 'busy', { attempt, retryAfter: event.retryAfter ?? null });
    }

    case 'RETRY':
      if (name === 'busy') return carry(state, 'sending', { attempt: (state.attempt ?? 1) + 1 });
      if (name !== 'failed') return state;
      // A failed example runs again; a failed upload is sent again, from the
      // first attempt, when its file passed the check.
      if (state.example) return carry(state, 'working', { ...since(event) });
      if (!canSend(state)) return state;
      return { name: 'sending', file: state.file, check: state.check, attempt: 1 };

    case 'CANCEL':
      if (!['sending', 'working', 'busy'].includes(name)) return state;
      if (!state.file || state.check === undefined) return initialState();
      return { name: 'chosen', file: state.file, check: state.check };

    case 'EXAMPLE':
      if (!['idle', 'chosen', 'interactive', 'failed'].includes(name)) return state;
      return carry({ file: state.file, check: state.check, example: true }, 'working', { ...since(event) });

    case 'RESPONSE':
      // The answer can arrive before the page heard that the upload ended.
      if (!(name === 'working' || name === 'sending') || event.response === undefined) return state;
      return carry(state, 'finishing', { response: event.response });

    case 'FINISHED':
      return name === 'finishing' ? carry(state, 'receipt') : state;

    case 'RECEIPT_DONE':
      return name === 'receipt' ? carry(state, 'flying') : state;

    case 'FLIGHT_DONE':
      return name === 'flying' ? carry(state, 'settling') : state;

    case 'SETTLED':
      return name === 'settling' ? carry(state, 'interactive') : state;

    case 'SKIP':
      return GUIDED.has(name) ? carry(state, 'interactive') : state;

    case 'REPLAY':
      return name === 'interactive' && state.response !== undefined ? carry(state, 'receipt') : state;

    case 'FAILED': {
      if (name === 'idle') return state;
      const out = { name: 'failed', file: state.file, check: state.check, error: event.error ?? null, stage: event.stage ?? name };
      if (state.example) out.example = true;
      return out;
    }

    case 'CLEAR':
      return ['chosen', 'interactive', 'failed'].includes(name) ? initialState() : state;

    default:
      return state;
  }
}
