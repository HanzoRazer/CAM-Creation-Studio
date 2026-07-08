# Feeds & Speeds Model

The feeds/speeds calculator produces a **starting point that requires operator
verification** — never a certified value. `calculate_feeds(...)` returns a
`FeedRecommendation` carrying the computed numbers, free-form notes/warnings, and
a list of coded `FeedDiagnostic` objects.

```
inputs (tool, flutes, rpm, chipload/material, woc, doc, limits)
        │
        ▼
calculate_feeds ──► FeedRecommendation { numbers + notes + warnings + diagnostics }
```

## Formulas

| Quantity | Formula | Units |
|---|---|---|
| Feed rate | `rpm × flutes × chipload` | mm/min |
| Surface speed | `π × tool_diameter × rpm` | mm/min |
| Chip-thinning factor | `1 / sqrt(1 − (1 − 2·woc/D)²)`, capped at 4 | ratio |
| Material removal rate | `woc × doc × feed_rate` | mm³/min |
| Spindle power (est.) | `(MRR / 60) × specific_energy` | W |
| Torque (est.) | `power_w × 60 / (2π · rpm)` | N·m |

Chip thinning is `1.0` at or above half-diameter width of cut and rises as the
cut gets thinner, capped at 4× to avoid runaway numbers. Power and torque use a
coarse specific-cutting-energy estimate (`J/mm³`, keyed by material with a generic
fallback) and are advisory sanity bounds, not a validated cutting-force model.

## `FeedRecommendation` fields

| Field | Meaning |
|---|---|
| `rpm`, `feed_rate`, `chipload`, `surface_speed` | Core computed values. |
| `chip_thinning_factor` | Radial thinning multiplier (1.0 when no WOC given). |
| `material_removal_rate` | mm³/min; `None` until WOC **and** DOC are supplied. |
| `spindle_power_kw`, `spindle_power_hp`, `torque_nm` | Advisory estimates; `None` until an MRR exists. |
| `power_w` | Back-compat watts (`spindle_power_kw × 1000`). |
| `notes` | Free-form advisory lines (always includes the operator-verification note). |
| `warnings` | Free-form warning strings (back-compat). |
| `diagnostics` | Coded `FeedDiagnostic { code, severity, message }` list. |

`surface_speed_m_min` is a convenience property. `as_dict()` gives a JSON-ready
shape; `FeedsResult` is a deprecated alias of `FeedRecommendation`.

## Diagnostic codes

| Code | Severity | Fires when |
|---|---|---|
| `ADVISORY_ONLY` | info | Always — every result is a starting point only. |
| `MISSING_DIAMETER_OR_SPEED` | warning | Tool diameter is missing/non-positive. |
| `RPM_EXCEEDS_MACHINE_LIMIT` | danger | `spindle_rpm > max_rpm`. |
| `POWER_EXCEEDS_MACHINE_LIMIT` | danger | Estimated power `> max_power_kw`. |
| `WOC_EXCEEDS_DIAMETER` | danger | Width of cut `> tool_diameter`. |
| `DOC_AGGRESSIVE` | warning | Depth of cut `> tool_diameter`. |
| `CHIPLOAD_HIGH` | warning | Chipload above the material's conservative high. |

Invalid inputs (`flutes <= 0`, `spindle_rpm <= 0`, no chipload and no material)
raise `ValueError` rather than producing a diagnostic — they are programming
errors, not advisory conditions.

## Presets

- **Materials** (`materials.py`) — conservative chipload ranges (mm/tooth) for
  softwood, hardwood, plywood, MDF, acrylic, aluminum, brass, mild steel,
  stainless, and general plastic. Aluminum, brass, mild steel, stainless,
  hardwood, softwood/MDF, and acrylic are the seven original HTML-calculator
  materials.
- **Machines** (`machines.py`) — starter profiles (generic router, desktop 3018,
  generic laser, Marlin printer, and a fact-limited BCAMCNC 2030CA placeholder)
  supplying RPM ceilings and work envelopes for bounds-checking.

All presets are advisory starting points, not certified machine or tooling data.
Always verify against your tooling manufacturer's numbers and your own test cuts.
