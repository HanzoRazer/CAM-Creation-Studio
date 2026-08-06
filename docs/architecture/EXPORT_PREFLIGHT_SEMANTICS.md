# Export Preflight Semantics

**Status:** Terminology ruling **and implementation contract**. Implemented by CS-009.
**Policy version:** `cs-export-preflight/1`
**Canonical entry point:** `cam_creation_studio.safety.run_export_preflight`
**Governing document:** [`../product-scope.md`](../product-scope.md)
**Related:** [`../safety-disclaimer.md`](../safety-disclaimer.md), `python/cam_creation_studio/safety/rules.py`
**Last verified:** 2026-08-05 · CS `db68f16`

> **This ruling stands on its own authority.** It introduces no new policy: it
> restates constraints already binding under `docs/product-scope.md` and already
> reflected throughout the codebase, and names the alternative term.
>
> [`CAM_CREATION_STUDIO_PRODUCT_BOUNDARY.md`](CAM_CREATION_STUDIO_PRODUCT_BOUNDARY.md)
> was ratified on 2026-08-05, but this document never depended on that outcome
> and does not depend on it now. If the boundary is later superseded, reopened
> by a §9.5 trigger, or rejected outright, this ruling is unaffected — its
> authority is the product constitution, not the CAM-CS-01 investigation.
> Changing it requires the separate governance decision described in §8.

---

## 1. The conflict this resolves

The CAM-CS-01 handoff (Decision 7) required a mandatory gate, and specified that
no output file may be marked **machine-ready** unless it passes. It further
proposed a `posts/` package with controller-named modules — `grbl.py`,
`mach3.py`, `mach4.py`, `linuxcnc.py`.

`docs/product-scope.md` opens by declaring itself the deciding authority:

> This is the constitutional scope document for CAM-Creation-Studio. When in
> doubt about whether something belongs in this project, this document decides.

It places out of scope: *"Certified post-processors and 'production-ready'
machine output"*, *"Automatic machining approval"*, and *"Real collision or
material-removal simulation"*. It states the required vocabulary:

> The app uses language like *machine output profiles*, *starter dialect
> profiles*, and *educational G-code templates* — never *production-ready post
> processor*, *machine-certified output*, or *safe to run*.

The shipped code says the same thing. `python/cam_creation_studio/safety/rules.py`:

```python
DISCLAIMER = (
    "CAM-Creation-Studio is an educational tool. It does not certify machine "
    "readiness, replace professional CAM validation, or guarantee safe machine "
    "execution. Generated G-code is a starting point; the preview is not a "
    "simulation. Always verify and air-cut before running."
)
```

**Resolution: the product constitution stands. The gate is renamed.** The
constitution is not amended by this pull request, and it must not be amended as a
side effect of implementing any workflow.

---

## 2. Prohibited claims

These must not appear in Creation Studio source, output, documentation, UI text,
diagnostics, artifact metadata, or commit messages:

```text
machine-ready
machine ready
safe to run
certified post processor
production-ready post processor
production-ready output
certified output
machine-certified
approved for machining
```

This applies regardless of which repository produced the underlying toolpath. If
Creation Studio packages a Toolbox-generated artifact, Creation Studio still does
not assert machine readiness about it.

### On automated enforcement

A grep-based lint for these phrases would not work, and it is worth recording why
so nobody builds one expecting it to help.

Swept on 2026-08-04, the repository contains roughly nineteen occurrences of the
prohibited vocabulary. **Every one outside this document is a negation** —
`gcode/dialects.py`: *"not certified post-processors … No guarantee the output is
safe to run"*; `gcode/generator.py`: *"NOT a certified post-processor and is NOT
guaranteed safe to run"*; `README.md`: *"A certified post-processor"* under a
"what this is not" heading; `product-scope.md`: the prohibition itself.

The constraint is on **affirmative claims**, and the phrase alone does not
distinguish an assertion from its denial. A naive matcher would flag the
constitution, this ruling, and every correct disclaimer in the codebase, and
maintaining its allowlist would cost more than the check returns.

The current state is therefore **compliant by review, not by tooling**, and this
document is the reviewer's reference.

The one near-miss previously on record — `cli/commands/generate.py` using
"machine-ready" non-negated in a comment about how an output *path* looks — was
resolved during CS-009, when that comment was edited anyway to describe the new
export boundary. It now reads "looks like a finished program." No affirmative use
of the prohibited vocabulary remains in the codebase.

---

## 3. Permitted vocabulary

From `docs/product-scope.md`, plus the preflight terms this ruling establishes:

```text
machine output profiles
starter dialect profiles
educational G-code templates
advisory
starting point
preview (never "simulation")
export preflight
export eligible / export blocking
dialect compatible
validation complete
```

---

## 4. Implementation

**Status: implemented (CS-009).** Policy version **`cs-export-preflight/1`**.

### Canonical entry point

```python
from cam_creation_studio.safety import run_export_preflight

result = run_export_preflight(gcode, config)
```

`python/cam_creation_studio/safety/preflight.py` owns this. It is the **only**
implementation; every export path calls it, and no policy logic lives in the CLI.
`gcode` is the artifact that would be written, `config` the generation context
(the same mapping `build_program` consumes). Neither is mutated.

### Result

```python
@dataclass(frozen=True, slots=True)
class ExportPreflightResult:
    export_allowed: bool
    blocking_findings: tuple[Diagnostic, ...]
    advisory_findings: tuple[Diagnostic, ...]
    policy_version: str
    disclaimer: str
    evaluated_rule_ids: tuple[str, ...]
    skipped_rule_ids: tuple[str, ...]
```

`export_allowed` is `True` exactly when `blocking_findings` is empty; advisory
findings never affect it. There is **no timestamp** — equal inputs must produce
equal results so fixtures stay stable and repeat evaluation is verifiably
identical. Findings are ordered by program location, then severity, then code,
then message, with program-wide findings first; nothing in the ordering consults
a dict, a set, or the filesystem.

Conventions followed: `Diagnostic` is reused unchanged (no second diagnostic
model); the four new codes live in the single registry at
`gcode/validator/codes.py` as `EXPORT_PREFLIGHT_CODES`, deliberately outside the
eleven `CANONICAL_CODES` that CS-003 promises; frozen dataclasses throughout, no
Pydantic; `disclaimer` carries `safety.rules.DISCLAIMER` rather than a new
string; no new runtime dependency.

### What blocks, and why that line is where it is

Preflight blocks **what Creation Studio can know is wrong** and advises on
**what only the operator can know**. Severity does not decide it — policy does.

| Blocking | Reason |
| --- | --- |
| `DUPLICATE_UNITS` | program declares both G20 and G21 |
| `ARC_WITHOUT_CENTER_OR_RADIUS` | arc geometry is unresolvable |
| `ARC_ON_NON_ARC_DIALECT` | unrepresentable for the selected dialect |
| `UNSUPPORTED_DIALECT` | target dialect is unknown |
| `EXPORT_EMPTY_ARTIFACT` | nothing to write |
| `EXPORT_NON_FINITE_VALUE` | NaN/Inf parameter no controller can honor |
| `EXPORT_UNIT_MISMATCH` | request asked one unit system, artifact emits another |
| `EXPORT_NON_POSITIVE_FEED` | feed move carrying `F <= 0` |

Everything else stays advisory — including `SPINDLE_OFF_WITH_CUTS`,
`NEGATIVE_Z_IN_LASER_MODE`, and `EXTRUSION_WITHOUT_HOTEND`, which are
`DiagnosticSeverity.DANGER`. Whether those are real hazards depends on a machine
Creation Studio cannot inspect. **Blocking on them would be an implicit claim to
machine authority, which §2 forbids** — so they are surfaced loudly and the
operator decides. Equally, absent information Creation Studio has never required
(machine travel, workholding, tool condition, firmware behavior) never
manufactures a blocker.

An unknown dialect is detected once, by the validator, and *reclassified* here.
Preflight adds no detection that an existing subsystem already performs.

### CLI behavior

`camstudio generate` runs preflight at the export boundary. Blocking findings
stop the write — no file is created, an existing file is left untouched — and
the command exits **`1`**, the established validation-failure code. (The order's
suggested `3` was not used: it already means *file error* in this CLI.) Reports
go to stderr so stdout stays pure G-code for redirection. With `--json`, a
blocked run still emits a machine-readable report on stdout carrying **no
`gcode` key**, so nothing downstream can mistake it for an approved artifact,
and that report is never written to `--output`.

One residual sharp edge: `camstudio generate job.json > part.gcode` with a
blocked program leaves an empty `part.gcode`, because the shell creates the file
before the command runs. Preflight cannot prevent that; stderr says plainly that
no G-code was written. Prefer `-o` over redirection.

---

## 5. What a successful preflight means

> The generated artifact passed the software's defined structural, configuration,
> and policy checks for export.

That is the entire claim.

### What it does not mean

A successful preflight does **not** assert that:

- the machine is correctly configured;
- the stock is correctly sized, secured, or fixtured;
- the selected tooling is appropriate for the material or operation;
- the controller will interpret every emitted command as expected;
- the operation is safe to execute;
- the output is certified in any sense;
- collision, gouging, or material removal has been checked.

### Relationship to validation

Creation Studio's existing validation (`gcode/validator/`) is **advisory and
never blocks** — that is stated in `models.Diagnostic`: *"One advisory validation
finding. Never blocks generation."*

Export preflight is a distinct, narrower thing: it may block **export**, never
generation and never preview. A failed preflight must still permit generation,
preview, and clearly-labeled diagnostic output. This preserves the existing
advisory posture while giving export a defined gate.

---

## 6. Disclaimer attachment

`safety.rules.DISCLAIMER` remains attached to:

- exported artifacts;
- validation results;
- preflight results, passing or failing;
- any packaged output.

A passing preflight does not remove, weaken, or supersede the disclaimer. There
is no state in which Creation Studio drops it.

---

## 7. Prior art in the Luthiers Toolbox

`services/api/app/cam/postprocessor_boundary.py` (CAM Dev Order 6C) already
implements a compatible posture, stated in its own docstring:

> Core rule:
>   - 6C postprocessor output is a report, not machine code.
>   - No G-code generation · No DXF generation · No file output ·
>     No executable machine instructions
>
> Gate semantics:
>   - GREEN: Export object operation supported, all checks pass
>   - YELLOW: Supported with cautions (tight margins, incomplete metadata)
>   - RED: Unsupported operation, unit mismatch, bounds violation, missing tooling

Its report-not-machine-code stance matches this constitution, and its
GREEN/YELLOW/RED tiers map onto the existing `DiagnosticSeverity`
(`info` / `warning` / `danger`). It is the leading shared-extraction candidate —
see [`CAM_CREATION_STUDIO_PRODUCT_BOUNDARY.md`](CAM_CREATION_STUDIO_PRODUCT_BOUNDARY.md) §5.

---

## 8. Changing this later

Making Creation Studio assert machine readiness would be a change to what the
product claims about safety, with liability consequences. It requires a separate,
explicit governance decision addressing at minimum:

- liability posture;
- controller qualification;
- post-processor certification;
- machine-profile verification;
- operator responsibility;
- test evidence sufficient to support the claim;
- versioning and revocation of certified profiles;
- documentation language throughout the product.

It must not occur as a side effect of implementing a fretboard workflow, or any
other workflow.
