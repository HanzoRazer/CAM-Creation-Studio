import { describe, it, expect } from 'vitest';
import {
  buildHeader,
  buildManualBody,
  buildEtchBody,
  buildFooter,
  buildProgram,
} from '../src/gcode/generator.js';
import { getDialect, listDialects } from '../src/gcode/dialects.js';

const cncConfig = {
  machine: 'genericCnc',
  units: 'mm',
  positioning: 'abs',
  home: true,
  spindleOn: true,
  spindleRpm: 12000,
  safeZ: 5,
};

const marlinConfig = {
  machine: 'marlin',
  units: 'mm',
  positioning: 'abs',
  home: true,
  hotend: 210,
  bed: 60,
  safeZ: 5,
};

describe('buildHeader', () => {
  it('Test 1 — CNC header contains units, positioning, home, spindle, safe Z', () => {
    const out = buildHeader(cncConfig).join('\n');
    for (const expected of ['G21', 'G90', 'G28', 'M3 S12000', 'G0 Z5']) {
      expect(out).toContain(expected);
    }
  });

  it('Test 2 — Marlin header contains heater sequence', () => {
    const out = buildHeader(marlinConfig).join('\n');
    for (const expected of ['G21', 'G90', 'M140', 'M104', 'M190', 'M109']) {
      expect(out).toContain(expected);
    }
  });

  it('declares inch units as G20 when units = in', () => {
    const out = buildHeader({ ...cncConfig, units: 'in' }).join('\n');
    expect(out).toContain('G20');
    expect(out).not.toContain('G21');
  });

  it('omits the home line when home is false', () => {
    const out = buildHeader({ ...cncConfig, home: false }).join('\n');
    expect(out).not.toContain('G28');
  });
});

describe('buildFooter', () => {
  it('Test 3 — CNC footer retracts, stops spindle, parks, and ends', () => {
    const out = buildFooter(cncConfig).join('\n');
    for (const expected of ['G0 Z5', 'M5', 'G0 X0 Y0', 'M30']) {
      expect(out).toContain(expected);
    }
  });

  it('Marlin footer turns heaters off and disables steppers', () => {
    const out = buildFooter(marlinConfig).join('\n');
    for (const expected of ['M104 S0', 'M140 S0', 'M84', 'M30']) {
      expect(out).toContain(expected);
    }
  });
});

describe('buildManualBody', () => {
  it('Test 4 — arc move emits I/J center words in order', () => {
    const moves = [{ type: 'G2', x: '10', y: '10', z: '', f: '', i: '5', j: '0' }];
    const out = buildManualBody(moves, cncConfig).join('\n');
    expect(out).toContain('G2 X10 Y10 I5 J0');
  });

  it('omits blank fields and only emits E on Marlin', () => {
    const moves = [{ type: 'G1', x: '40', y: '', z: '-0.5', f: '800', e: '2' }];
    const cnc = buildManualBody(moves, cncConfig).join('\n');
    expect(cnc).toContain('G1 X40 Z-0.5 F800');
    expect(cnc).not.toContain('E2'); // CNC has no extruder
    const marlin = buildManualBody(moves, marlinConfig).join('\n');
    expect(marlin).toContain('E2');
  });
});

describe('buildEtchBody', () => {
  const square = [{ poly: [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }] }];

  it('power strategy toggles the beam per segment', () => {
    const cfg = { machine: 'laserGrbl', safeZ: 5, etch: { control: 'power', feed: 600, power: 200 } };
    const out = buildEtchBody(square, cfg).join('\n');
    expect(out).toContain('M3 S200');
    expect(out).toContain('M5');
    expect(out).toContain('F600');
  });

  it('depth strategy plunges to engrave Z and retracts', () => {
    const cfg = { machine: 'genericCnc', safeZ: 5, etch: { control: 'depth', feed: 600, engraveZ: -0.2 } };
    const out = buildEtchBody(square, cfg).join('\n');
    expect(out).toContain('G1 Z-0.2 F300');
    expect(out).toContain('G0 Z5');
  });

  it('emits a friendly note when there are no burn regions', () => {
    const cfg = { machine: 'laserGrbl', safeZ: 5, etch: { control: 'power' } };
    const out = buildEtchBody([], cfg).join('\n');
    expect(out).toContain('no burn regions');
  });
});

describe('buildProgram', () => {
  it('assembles header, body, and footer for a manual job', () => {
    const job = { mode: 'manual', moves: [{ type: 'G1', x: '10', y: '0', f: '800' }] };
    const program = buildProgram(cncConfig, job);
    expect(program).toContain('; --- HEADER ---');
    expect(program).toContain('; --- BODY ---');
    expect(program).toContain('; --- FOOTER ---');
    expect(program.indexOf('HEADER')).toBeLessThan(program.indexOf('BODY'));
    expect(program.indexOf('BODY')).toBeLessThan(program.indexOf('FOOTER'));
  });
});

describe('dialects', () => {
  it('resolves the cnc alias to genericCnc', () => {
    expect(getDialect('cnc').id).toBe('genericCnc');
  });

  it('throws on an unknown dialect', () => {
    expect(() => getDialect('nope')).toThrow(/Unknown dialect/);
  });

  it('ships marlin, genericCnc, and laserGrbl profiles', () => {
    const ids = listDialects().map((d) => d.id).sort();
    expect(ids).toEqual(['genericCnc', 'laserGrbl', 'marlin']);
  });
});
