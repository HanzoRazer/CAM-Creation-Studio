// units.js — unit conversion and normalization helpers.
// Educational tool: we keep units explicit everywhere and never guess.

import { parseNumberOrNull, roundForGcode } from './numbers.js';

export const MM_PER_INCH = 25.4;

/** Convert millimetres to inches. */
export function mmToIn(mm) {
  return mm / MM_PER_INCH;
}

/** Convert inches to millimetres. */
export function inToMm(inch) {
  return inch * MM_PER_INCH;
}

/**
 * Normalize a {value, units} pair into the requested target units.
 * Units are the simple strings used across the app: 'mm' | 'in'.
 * @param {number} value
 * @param {'mm'|'in'} from
 * @param {'mm'|'in'} to
 * @returns {number}
 */
export function normalizeUnits(value, from, to) {
  if (from === to) return value;
  if (from === 'in' && to === 'mm') return inToMm(value);
  if (from === 'mm' && to === 'in') return mmToIn(value);
  throw new Error(`normalizeUnits: unsupported units ${from} -> ${to}`);
}

/**
 * Format a numeric value with its unit suffix for display, rounding sensibly.
 * Returns '' when the value cannot be parsed.
 * @param {unknown} value
 * @param {'mm'|'in'} units
 * @param {number} [decimals]
 */
export function formatUnitValue(value, units, decimals = units === 'in' ? 4 : 3) {
  const n = parseNumberOrNull(value);
  if (n === null) return '';
  return `${roundForGcode(n, decimals)} ${units}`;
}

/** The G-code word that declares these units: G21 (mm) or G20 (inch). */
export function unitsCode(units) {
  return units === 'in' ? 'G20' : 'G21';
}
