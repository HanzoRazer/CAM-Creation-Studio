// handoff.js — feeds/speeds → Creator handoff contract.
//
// The Feeds & Speeds calculator (a separate app, archived for a later phase)
// writes a small advisory payload to localStorage under `gcodeHandoff`. The
// Creator detects it, shows a banner, and can apply the suggested spindle speed
// and feed rate. This module is the DOM-free, storage-agnostic core of that
// behavior so it can be unit-tested without a browser.
//
// Handoff payload shape (all advisory — "suggested starting point"):
//   { rpm: number, feed: number, units: 'mm'|'in', material?: string }

export const HANDOFF_KEY = 'gcodeHandoff';

/**
 * Read and validate a handoff payload from a Storage-like object.
 * Returns the parsed handoff, or null when absent/invalid. Never throws.
 * @param {Storage} storage  e.g. window.localStorage
 * @returns {{rpm:number, feed:number, units:string, material?:string}|null}
 */
export function readHandoff(storage) {
  if (!storage) return null;
  try {
    const raw = storage.getItem(HANDOFF_KEY);
    if (!raw) return null;
    const h = JSON.parse(raw);
    // A valid handoff must at least carry an rpm (mirrors the original guard).
    return h && h.rpm ? h : null;
  } catch (e) {
    return null;
  }
}

/** Remove the handoff payload from storage. Never throws. */
export function clearHandoff(storage) {
  if (!storage) return;
  try {
    storage.removeItem(HANDOFF_KEY);
  } catch (e) {
    /* ignore */
  }
}

/** Human-readable summary for the banner, e.g. "S18000 RPM · F1200 mm/min · MDF". */
export function handoffText(handoff) {
  if (!handoff) return '';
  const rate = handoff.units === 'mm' ? 'mm/min' : 'in/min';
  let text = `S${handoff.rpm} RPM · F${handoff.feed} ${rate}`;
  if (handoff.material) text += ` · ${handoff.material}`;
  return text;
}

/** True when a move type is a cutting move that takes a feed rate. */
function isCutMove(type) {
  return type === 'G1' || type === 'G2' || type === 'G3';
}

/**
 * Compute the state patch produced by applying a handoff. Pure: returns a new
 * partial-state object and does not mutate `state`.
 *
 * Effects (mirrors the original Creator):
 *  - switch to CNC mode
 *  - set spindle RPM and etch feed from the handoff
 *  - set units from the handoff
 *  - fill the feed on any cut move that is currently missing/non-positive
 *
 * @param {Object} state  Current Creator state ({ moves, ... }).
 * @param {Object} handoff  Validated handoff payload.
 * @returns {Object} partial state to merge into the Creator state.
 */
export function applyHandoffToState(state, handoff) {
  const moves = (state.moves || []).map((m) => {
    const missingFeed = m.f === '' || m.f == null || Number(m.f) <= 0;
    if (isCutMove(m.type) && missingFeed) return { ...m, f: String(handoff.feed) };
    return m;
  });
  return {
    machine: 'genericCnc',
    spindleRpm: String(handoff.rpm),
    etchFeed: String(handoff.feed),
    units: handoff.units === 'mm' ? 'mm' : 'in',
    moves,
  };
}
