# Feeds & Speeds Basics (Advisory)

> **Status: planned for a later step.** The feeds/speeds calculator and presets
> are not implemented in this phase. This page records the intended approach so
> the advisory framing is locked in before any numbers ship.

Feeds and speeds in CAM-Creation-Studio will always be a **suggested starting
point that requires operator verification** — never a hard claim.

## The two formulas we start from

```text
Feed rate   = RPM × flutes × chipload
Surface speed = π × tool diameter × RPM
```

Units are kept explicit everywhere (mm vs. inch, mm/min vs. in/min). A 1/4"
tool, for example, normalizes to **6.35 mm**.

## Worked example

```text
RPM      = 12000
flutes   = 2
chipload = 0.05 mm
=> feed  = 12000 × 2 × 0.05 = 1200 mm/min
```

## Advisory rules we will follow

- Every output is labeled **"Suggested starting point — requires operator
  verification."**
- Material presets carry **conservative chipload ranges**, not exact claims.
- Tool and machine presets are starter profiles you can edit.
- The calculator emits **notes and warnings**, not approvals.

## Handoff to the Creator

The Creator already supports an **advisory handoff**: when a Feeds & Speeds
calculator writes a payload to `localStorage` under the key `gcodeHandoff`
(shape `{ rpm, feed, units, material }`), the Creator shows a banner offering to
**Apply S & F**. Applying it switches to CNC mode, sets the spindle RPM, etch
feed, and units, and fills the feed on any cut move that is missing one. The
contract lives in [`src/handoff/handoff.js`](../src/handoff/handoff.js) and is
unit-tested. The calculator side itself is archived for a later phase.

See [safety-disclaimer.md](safety-disclaimer.md) and
[product-scope.md](product-scope.md) for why this stays advisory.
