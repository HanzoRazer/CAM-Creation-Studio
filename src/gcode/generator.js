// generator.js — pure G-code generation.
//
// Ported from the original single-file app's buildManualGcode/buildEtchGcode,
// restructured into composable, DOM-free functions that take plain objects:
//
//   buildHeader(config)            -> string[]
//   buildManualBody(moves, config) -> string[]
//   buildEtchBody(paths, config)   -> string[]
//   buildFooter(config)            -> string[]
//   buildProgram(config, job)      -> string   (the full program)
//
// Nothing here touches the DOM, the canvas, or app state. Inputs are plain
// objects so the same functions back both the UI and the tests.
//
// IMPORTANT: output is an EDUCATIONAL starting point. It is NOT a certified
// post-processor and is NOT guaranteed safe to run. Always verify before use.

import { formatLine, sectionLine } from './formatter.js';
import { getDialect } from './dialects.js';
import { unitsCode } from '../shared/units.js';
import { roundForGcode, parseNumberOrNull } from '../shared/numbers.js';

/** Render a dialect line descriptor ({cmd, words, comment}) to a string. */
function renderExtra(d) {
  return formatLine(d.cmd, d.words || {}, d.comment || '');
}

/** Safe Z fallback: use the configured value or 0 when blank/invalid. */
function safeZ(config) {
  const z = parseNumberOrNull(config.safeZ);
  return z === null ? 0 : z;
}

/**
 * Build the program header: units, positioning, optional home, dialect-specific
 * startup (heaters / spindle / beam), then a rapid to safe Z.
 * @param {Object} config
 * @returns {string[]}
 */
export function buildHeader(config) {
  const dialect = getDialect(config.machine);
  const lines = [sectionLine('HEADER')];

  lines.push(
    config.units === 'in'
      ? formatLine('G20', {}, 'units = inch')
      : formatLine('G21', {}, 'units = mm'),
  );
  lines.push(
    config.positioning === 'rel'
      ? formatLine('G91', {}, 'relative positioning')
      : formatLine('G90', {}, 'absolute positioning'),
  );
  if (config.home) lines.push(formatLine('G28', {}, 'home all axes'));

  for (const extra of dialect.headerExtras(config)) lines.push(renderExtra(extra));

  lines.push(formatLine('G0', { Z: safeZ(config) }, 'move to safe height'));
  return lines;
}

/**
 * Build the manual-move body. Each move is { type, x, y, z, f, e, i, j } with
 * string-or-number fields; blank fields are omitted from the line.
 * @param {Array<Object>} moves
 * @param {Object} config
 * @returns {string[]}
 */
export function buildManualBody(moves, config) {
  const dialect = getDialect(config.machine);
  const isMarlin = dialect.id === 'marlin';
  const lines = [sectionLine('BODY')];

  for (const m of moves) {
    const isArc = m.type === 'G2' || m.type === 'G3';
    const words = { X: m.x, Y: m.y, Z: m.z };
    if (isArc) {
      words.I = m.i;
      words.J = m.j;
    }
    if (isMarlin) words.E = m.e;
    words.F = m.f;
    lines.push(formatLine(m.type, words));
  }
  return lines;
}

/**
 * Build an image-etch body from neutral path segments. Each path is
 * { poly: [{x, y}, ...] }. Two cut strategies, matching the original app:
 *   - control 'power': beam toggled per segment via M3 S / M5
 *   - control 'depth': plunge to engraveZ, cut, retract to safe Z
 * @param {Array<{poly: Array<{x:number,y:number}>}>} paths
 * @param {Object} config  Etch settings live on config.etch.
 * @returns {string[]}
 */
export function buildEtchBody(paths, config) {
  const etch = config.etch || {};
  const power = etch.control !== 'depth';
  const F = etch.feed ?? 600;
  const S = etch.power ?? 200;
  const engraveZ = etch.engraveZ ?? -0.2;
  const z = safeZ(config);
  const r = (n) => roundForGcode(n, 3);

  const lines = [sectionLine('TOOLPATH')];
  if (!paths.length) {
    lines.push('; (no burn regions — load an image or lower the cutoff)');
    return lines;
  }

  for (const seg of paths) {
    const poly = seg.poly;
    const a = poly[0];
    if (power) {
      lines.push(formatLine('G0', { X: r(a.x), Y: r(a.y) }));
      lines.push(formatLine('M3', { S }));
    } else {
      lines.push(formatLine('G0', { Z: z }));
      lines.push(formatLine('G0', { X: r(a.x), Y: r(a.y) }));
      lines.push(formatLine('G1', { Z: engraveZ, F: 300 }));
    }
    for (let k = 1; k < poly.length; k++) {
      const p = poly[k];
      lines.push(formatLine('G1', { X: r(p.x), Y: r(p.y), F: k === 1 ? F : undefined }));
    }
    lines.push(power ? formatLine('M5') : formatLine('G0', { Z: z }));
  }
  return lines;
}

/**
 * Build the footer: retract to safe Z, dialect-specific shutdown (heaters off /
 * spindle off / beam off), park at origin, end the program.
 * @param {Object} config
 * @returns {string[]}
 */
export function buildFooter(config) {
  const dialect = getDialect(config.machine);
  const lines = [sectionLine('FOOTER')];
  lines.push(formatLine('G0', { Z: safeZ(config) }, 'retract'));
  for (const extra of dialect.footerExtras(config)) lines.push(renderExtra(extra));
  lines.push(formatLine('G0', { X: 0, Y: 0 }, 'park'));
  lines.push(formatLine('M30', {}, 'end of program'));
  return lines;
}

/**
 * Assemble a complete program from a config + a job.
 *   job = { mode: 'manual', moves: [...] }
 *   job = { mode: 'etch',   paths: [...] }   (etch settings on config.etch)
 * @param {Object} config
 * @param {Object} job
 * @returns {string}
 */
export function buildProgram(config, job) {
  const body =
    job.mode === 'etch'
      ? buildEtchBody(job.paths || [], config)
      : buildManualBody(job.moves || [], config);

  return [...buildHeader(config), '', ...body, '', ...buildFooter(config)].join('\n');
}

export { unitsCode };
