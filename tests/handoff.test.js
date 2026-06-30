import { describe, it, expect } from 'vitest';
import {
  HANDOFF_KEY,
  readHandoff,
  clearHandoff,
  handoffText,
  applyHandoffToState,
} from '../src/handoff/handoff.js';

// Minimal in-memory Storage stand-in.
function makeStorage(initial = {}) {
  const data = { ...initial };
  return {
    getItem: (k) => (k in data ? data[k] : null),
    setItem: (k, v) => { data[k] = String(v); },
    removeItem: (k) => { delete data[k]; },
    _data: data,
  };
}

const handoff = { rpm: 18000, feed: 1200, units: 'mm', material: 'MDF' };

describe('readHandoff', () => {
  it('reads and parses a valid payload', () => {
    const storage = makeStorage({ [HANDOFF_KEY]: JSON.stringify(handoff) });
    expect(readHandoff(storage)).toEqual(handoff);
  });

  it('returns null when absent', () => {
    expect(readHandoff(makeStorage())).toBeNull();
  });

  it('returns null for malformed JSON instead of throwing', () => {
    const storage = makeStorage({ [HANDOFF_KEY]: '{not json' });
    expect(readHandoff(storage)).toBeNull();
  });

  it('returns null when the payload lacks rpm', () => {
    const storage = makeStorage({ [HANDOFF_KEY]: JSON.stringify({ feed: 1200 }) });
    expect(readHandoff(storage)).toBeNull();
  });
});

describe('clearHandoff', () => {
  it('removes the payload from storage', () => {
    const storage = makeStorage({ [HANDOFF_KEY]: JSON.stringify(handoff) });
    clearHandoff(storage);
    expect(readHandoff(storage)).toBeNull();
  });
});

describe('handoffText', () => {
  it('formats rpm, feed, units, and material', () => {
    expect(handoffText(handoff)).toBe('S18000 RPM · F1200 mm/min · MDF');
  });

  it('uses in/min for inch units and omits a missing material', () => {
    expect(handoffText({ rpm: 12000, feed: 30, units: 'in' })).toBe('S12000 RPM · F30 in/min');
  });

  it('returns empty string for no handoff', () => {
    expect(handoffText(null)).toBe('');
  });
});

describe('applyHandoffToState', () => {
  const baseState = {
    machine: 'marlin',
    units: 'in',
    moves: [
      { id: 1, type: 'G0', x: '0', y: '0', f: '' },
      { id: 2, type: 'G1', x: '40', y: '0', f: '' }, // missing feed -> filled
      { id: 3, type: 'G1', x: '40', y: '30', f: '800' }, // existing feed -> kept
      { id: 4, type: 'G2', x: '0', y: '30', f: '0' }, // non-positive -> filled
    ],
  };

  it('switches to CNC and sets spindle/feed/units from the handoff', () => {
    const patch = applyHandoffToState(baseState, handoff);
    expect(patch.machine).toBe('genericCnc');
    expect(patch.spindleRpm).toBe('18000');
    expect(patch.etchFeed).toBe('1200');
    expect(patch.units).toBe('mm');
  });

  it('fills missing/non-positive feeds on cut moves only, leaving others untouched', () => {
    const patch = applyHandoffToState(baseState, handoff);
    expect(patch.moves[0].f).toBe(''); // G0 rapid: untouched
    expect(patch.moves[1].f).toBe('1200'); // G1 missing feed: filled
    expect(patch.moves[2].f).toBe('800'); // G1 existing feed: kept
    expect(patch.moves[3].f).toBe('1200'); // G2 zero feed: filled
  });

  it('does not mutate the input state', () => {
    const before = JSON.stringify(baseState);
    applyHandoffToState(baseState, handoff);
    expect(JSON.stringify(baseState)).toBe(before);
  });
});
