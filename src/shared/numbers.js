// numbers.js — numeric sanitizers shared across modules.
// All helpers are pure and DOM-free.

/**
 * Parse a value into a finite number, or return null when it cannot be parsed.
 * Empty strings, null, undefined, and NaN all collapse to null.
 * @param {unknown} value
 * @returns {number|null}
 */
export function parseNumberOrNull(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  const str = String(value).trim();
  if (str === '') return null;
  const n = Number(str);
  return Number.isFinite(n) ? n : null;
}

/**
 * Clamp a number into the inclusive [min, max] range.
 * @param {number} n
 * @param {number} min
 * @param {number} max
 * @returns {number}
 */
export function clampNumber(n, min, max) {
  if (n < min) return min;
  if (n > max) return max;
  return n;
}

/**
 * Round a number to a fixed precision suitable for G-code output (default 3 dp)
 * and strip any trailing zeros so "10.000" becomes "10".
 * @param {number} n
 * @param {number} [decimals=3]
 * @returns {number}
 */
export function roundForGcode(n, decimals = 3) {
  if (!Number.isFinite(n)) return 0;
  const factor = Math.pow(10, decimals);
  return Math.round(n * factor) / factor;
}

/**
 * True when value parses to a number strictly greater than zero.
 * @param {unknown} value
 * @returns {boolean}
 */
export function isPositiveNumber(value) {
  const n = parseNumberOrNull(value);
  return n !== null && n > 0;
}
