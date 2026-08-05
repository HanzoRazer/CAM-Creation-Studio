# CAM-CS-01 — Reference Artifact Search Record

**Status:** Increment 1 deliverable (documentation and evidence only)
**Conclusion:** `REFERENCE_ARTIFACT_NOT_LOCATED`
**Search date:** 2026-08-04

The CAM-CS-01 handoff treats a standalone **Fretboard G-Code Generator** HTML
application as the behavioral reference and feature-parity baseline. This
document records the search for that artifact and its outcome.

**No file matching the described application was located.** Nothing was archived,
and no hash was recorded as belonging to the requested application.

---

## 1. Feature set the search was looking for

Derived from the handoff's own description of the application (§2, §4.1, §7,
§9.14). These are **product descriptions**, evidence tier 7 — they are what the
search targeted, not verified behavior.

Stock preparation and flattening · fret-slot machining (flat and radiused) ·
constant and compound radius surfacing · nut slot and zero fret · position
markers (dot, rectangle, square, oval, custom SVG) · custom SVG inlays · male
plug generation · LightBurn-oriented output · holding tabs · multiscale /
fan-fret layout · Rule of 18 · machine and controller presets covering GRBL,
Marlin, LinuxCNC, Mach3, Mach4 · toolpath preview and simulation · separate and
combined output packaging · operator warnings.

---

## 2. Locations searched

| Location | Method | Result |
| --- | --- | --- |
| `C:\Users\thepr\Downloads` (recursive, depth 4) | filename match `*fret*` | 38 hits, all rejected — see §3 |
| `C:\Users\thepr\Downloads` (top level) | all `*.html` > 20 KB, sorted by recency | 40 files reviewed by name; no fretboard G-code application |
| `C:\Users\thepr\Desktop` | recursive `*.html` matching `fret|slot|board|gcode|g-code` | no matches |
| `C:\Users\thepr\Documents` | recursive `*.html`, same pattern | only `luthiers-toolbox` coverage-report HTML and a `fret_wire_path_pack` copy |
| `C:\Users\thepr\Downloads\CAM-Creation-Studio` | full repository tree | no fretboard artifact; `archive/original-html/` holds only G-code Creator, Feeds & Speeds Calculator, Preview Dashboard, Quick-Start Manual |
| `C:\Users\thepr\Downloads\CNC-Production-Shop` | glob `*fret*` | `fretboard/__init__.py` (2-line stub) and `fixtures/cnc_cost/fretboard_slotting_v1.json` (a cost fixture) |
| `C:\Users\thepr\Downloads\luthiers-toolbox` | `prototypes/`, `artifacts/`, `templates/`, `local/`, `exports/` recursive `*.html` | one file, `prototypes/features.html` (100 KB) — not a fretboard generator |
| `C:\Users\thepr\Downloads\Instruments`, `Master-All-Strings` | recursive `*.html`, same pattern | no matches |

---

## 3. Filename candidates and why each was rejected

### 3.1 `Downloads/files (3)/guitar_cnc_fret_generator.html`

- Size 37,818 B · modified 2025-12-08
- SHA-256 `1f39110dce572e5723679c52c57b522b491f9a4a935a4b14d63b7539d66ce557`

**Rejected.** A case-insensitive scan for the feature vocabulary returned **7
occurrences of `radius` and nothing else**. Zero occurrences of: `lightburn`,
`compound`, `multiscale`, `fan fret`, `holding tab`, `flatten`, `male plug`,
`plug`, `inlay`, `marker`, `mach3`, `mach4`, `linuxcnc`, `marlin`, `grbl`,
`simulat`, `rule of 18`, `17.817`, `zero fret`.

The name is the closest match found anywhere on the filesystem, but the file does
not implement the described application.

### 3.2 `Downloads/files - 2026-03-19T213759.333/fret_wire_path_pack.html`

- Size 40,984 B · modified 2026-03-21
- SHA-256 `930f8d9f5038b807e2e108c0679d874a205d2eb87ed050ce0c0a73c87d64c157`

**Rejected.** Same scan returned **11 × `radius` and 1 × `Radius`**, nothing else
from the vocabulary. Subject matter is fret wire, not fretboard CAM. A duplicate
copy exists under `Documents/Codex/.../docs/archive/photo_vectorizer_patches/`.

Hashes are recorded **solely so these two files can be positively re-identified
and excluded from future searches.** Neither is the requested application, and
neither has been archived as such.

### 3.3 `CNC-Production-Shop/fretboard/`

**Rejected — not an implementation.** The package contains a single
`__init__.py`:

```python
"""Fretboard tools — Fret slot calculation and layout."""

__version__ = "0.1.0"
```

A docstring and a version string. No code.

### 3.4 `luthiers-toolbox/prototypes/features.html`

**Rejected.** A toolbox feature page, not a fretboard G-code generator.

---

## 4. Conclusion

```text
REFERENCE_ARTIFACT_NOT_LOCATED
```

Per Ruling 1, until the actual application is supplied and positively identified:

- the standalone application is treated as **UNAVAILABLE**;
- no claim is made that it was archived;
- no hash is presented as belonging to it;
- no browser replay harness has been built against a guessed candidate;
- no Python behavior is classified as `PARITY`;
- every capability known only from the handoff prose is classified
  `DESCRIBED_NOT_OBSERVED` in
  [`FRETBOARD_IMPLEMENTATION_COMPARISON_MATRIX.md`](FRETBOARD_IMPLEMENTATION_COMPARISON_MATRIX.md).

Removed from the first increment accordingly: the HTML behavior extractor, the
browser reference execution harness, standalone golden masters, the G-code
canonicalizer, the standalone-versus-Python toolpath comparator, the parity
closeout tranche, and any behavioral freeze against the missing application.

---

## 5. Restoration procedure

If the application is later supplied, follow Ruling 1 §"Conditional restoration":

1. Record its original filename and source location.
2. Copy it into a read-only evidence location (`archive/original-html/` is the
   established convention in this repository).
3. Calculate and record its SHA-256.
4. Confirm it runs offline.
5. Inventory its **actual** feature set — not the described one.
6. Add it as one evidence source **without** retroactively rewriting this record
   or reclassifying earlier findings.

It does not automatically supersede canonical repository implementations. Per the
evidence hierarchy a browser artifact ranks below executed tests, explicit
authority declarations, active call paths, and schemas.

---

## 6. Note on what the search did find

The search did not find the HTML application, but it did establish that a real,
executable, Python fret-position oracle exists in the Luthiers Toolbox:
`services/api/tests/test_golden_fret_positions.py`, asserting golden values for
four scale lengths against
`app.instrument_geometry.neck.fret_math.compute_fret_positions_mm`.

Per Ruling 3 this is recorded as the strongest currently available implementation
reference. It is **not** declared the parity oracle. See
[`CAM_CS_01_AUTHORITY_COLLISION_AUDIT.md`](CAM_CS_01_AUTHORITY_COLLISION_AUDIT.md) §5.
