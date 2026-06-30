// formatter.js — normalize G-code line output.
//
// A G-code line is a command word (G1, M3, ...) followed by parameter "words"
// (X10, Y5, F800) and an optional trailing comment. This module is the single
// place that decides spacing, number rounding, and comment style so output is
// consistent everywhere.

import { roundForGcode } from '../shared/numbers.js';

/**
 * Format a numeric parameter value for output: round for G-code and stringify
 * without a trailing ".0". Non-finite values fall back to the raw string.
 */
function formatValue(value, decimals) {
  if (typeof value === 'number') return String(roundForGcode(value, decimals));
  // Allow already-formatted strings (e.g. "-0.5") to pass through untouched.
  return String(value);
}

/**
 * Build a single G-code line.
 *
 *   formatLine('G1', { X: 10, Y: 5, F: 800 }, 'cut move')
 *     -> 'G1 X10 Y5 F800 ; cut move'
 *
 * @param {string} command  Command word, e.g. 'G1', 'M3', 'G0'.
 * @param {Object} [words]  Map of axis/parameter letters to values. Keys with
 *                          null/undefined/'' values are skipped. Insertion order
 *                          is preserved.
 * @param {string} [comment] Optional comment; emitted as '; comment'.
 * @param {Object} [opts]
 * @param {number} [opts.decimals=3] Rounding precision for numeric values.
 * @returns {string}
 */
export function formatLine(command, words = {}, comment = '', opts = {}) {
  const decimals = opts.decimals ?? 3;
  const parts = [];
  if (command) parts.push(command);
  for (const [letter, value] of Object.entries(words)) {
    if (value === null || value === undefined || value === '') continue;
    parts.push(`${letter}${formatValue(value, decimals)}`);
  }
  let line = parts.join(' ');
  if (comment) line = line ? `${line} ; ${comment}` : `; ${comment}`;
  return line;
}

/** Emit a standalone comment line: '; text'. */
export function commentLine(text) {
  return `; ${text}`;
}

/** Emit a section banner used throughout the generated programs. */
export function sectionLine(title) {
  return `; --- ${title} ---`;
}
