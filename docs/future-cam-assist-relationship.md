# Future Relationship to CAM Assist

This document records the boundary between CAM Assist and CAM-Creation-Studio.
It exists so the boundary is **documented but not implemented** in this phase.

## The boundary

> **CAM Assist** owns manufacturing intent, review, risk, assumptions, and
> traceability.
>
> **CAM-Creation-Studio** owns execution-adjacent authoring, education,
> feeds/speeds, preview, and G-code learning.

### CAM Assist does **not** own (in this project)

- G-code
- Feeds and speeds
- Simulation
- Machine readiness
- Post-processing
- Execution claims

## Future optional interface

A future, **one-way, optional** relationship may look like this:

```text
CAM Assist
  → Production Shop Handoff
  → CAM-Creation-Studio
```

`Production Shop Handoff` may later be imported as **advisory context** only —
something CAM-Creation-Studio can read to pre-fill or sanity-check authoring,
never something it depends on or enforces.

## What is true today

- Do **not** merge the repositories.
- **No dependency exists in the current phase.**
- No CAM Assist imports, parsing, dependency, or schema enforcement.

Any future link must be introduced as a **stable, optional contract** — and only
in a later phase, deliberately, not as a side effect of this work.
