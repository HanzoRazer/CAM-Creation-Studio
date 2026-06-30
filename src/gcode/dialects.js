// dialects.js — starter dialect profiles.
//
// These are EDUCATIONAL "starter dialect profiles", not certified
// post-processors. They describe how each machine family tends to open and
// close a program and which words it expects. They make no guarantee that the
// output is safe to run on any specific machine.
//
// Each profile exposes:
//   id, label          identity
//   allowedAxes        axis letters this family understands
//   defaultUnits       'mm' | 'in'
//   supportsArcs       whether G2/G3 are idiomatic here
//   startupComment     short note for the header banner
//   headerExtras(cfg)  machine-specific header line descriptors
//   footerExtras(cfg)  machine-specific shutdown line descriptors
//
// A "line descriptor" is { cmd, words?, comment? } and is rendered by the
// generator through formatter.formatLine(). Builders are pure and DOM-free.

import { isPositiveNumber } from '../shared/numbers.js';

/** Marlin-style 3D printer: heated nozzle + bed, extrusion on the E axis. */
const marlin = {
  id: 'marlin',
  label: 'Marlin · 3D Printer',
  allowedAxes: ['X', 'Y', 'Z', 'E', 'F'],
  defaultUnits: 'mm',
  supportsArcs: false, // many Marlin builds ship without arc support
  commentStyle: ';',
  startupComment: 'heat up, home, move to safe Z',
  headerExtras(cfg) {
    const lines = [];
    const bed = isPositiveNumber(cfg.bed) ? cfg.bed : null;
    const hotend = isPositiveNumber(cfg.hotend) ? cfg.hotend : null;
    if (bed !== null) lines.push({ cmd: 'M140', words: { S: bed }, comment: 'set bed temp' });
    if (hotend !== null) lines.push({ cmd: 'M104', words: { S: hotend }, comment: 'set hotend temp' });
    if (bed !== null) lines.push({ cmd: 'M190', words: { S: bed }, comment: 'wait for bed' });
    if (hotend !== null) lines.push({ cmd: 'M109', words: { S: hotend }, comment: 'wait for hotend' });
    return lines;
  },
  footerExtras(cfg) {
    const lines = [{ cmd: 'M104', words: { S: 0 }, comment: 'hotend off' }];
    if (isPositiveNumber(cfg.bed)) lines.push({ cmd: 'M140', words: { S: 0 }, comment: 'bed off' });
    lines.push({ cmd: 'M84', comment: 'disable steppers' });
    return lines;
  },
};

/** Generic 3-axis CNC mill/router: rotating spindle, M3/M5 control. */
const genericCnc = {
  id: 'genericCnc',
  label: 'CNC Mill',
  allowedAxes: ['X', 'Y', 'Z', 'I', 'J', 'F'],
  defaultUnits: 'mm',
  supportsArcs: true,
  commentStyle: ';',
  startupComment: 'home, start spindle, move to safe Z',
  headerExtras(cfg) {
    if (!cfg.spindleOn) return [];
    return [{ cmd: 'M3', words: { S: cfg.spindleRpm ?? 0 }, comment: 'spindle on' }];
  },
  footerExtras(cfg) {
    return cfg.spindleOn ? [{ cmd: 'M5', comment: 'spindle off' }] : [];
  },
};

/** GRBL-style laser/diode engraver: beam controlled via M3/M5 + S power. */
const laserGrbl = {
  id: 'laserGrbl',
  label: 'Laser · GRBL',
  allowedAxes: ['X', 'Y', 'F'],
  defaultUnits: 'mm',
  supportsArcs: true,
  commentStyle: ';',
  startupComment: 'home, beam off, move to safe Z',
  headerExtras() {
    return [{ cmd: 'M5', comment: 'beam off' }];
  },
  footerExtras() {
    return [{ cmd: 'M5', comment: 'beam off' }];
  },
};

const REGISTRY = { marlin, genericCnc, laserGrbl };

// Backwards-compatible alias: the original app stored the CNC machine as 'cnc'.
const ALIASES = { cnc: 'genericCnc', laser: 'laserGrbl' };

/**
 * Look up a dialect profile by id (or known alias). Throws on unknown ids so
 * mistakes surface loudly rather than producing silent wrong output.
 * @param {string} id
 */
export function getDialect(id) {
  const key = REGISTRY[id] ? id : ALIASES[id];
  const dialect = REGISTRY[key];
  if (!dialect) throw new Error(`Unknown dialect: ${id}`);
  return dialect;
}

/** List all available dialect profiles. */
export function listDialects() {
  return Object.values(REGISTRY);
}

export { marlin, genericCnc, laserGrbl, REGISTRY, ALIASES };
