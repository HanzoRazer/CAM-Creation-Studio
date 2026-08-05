# Export Preflight Semantics

**Status:** Terminology ruling. Documentation only — no code is added by this increment.
**Governing document:** [`../product-scope.md`](../product-scope.md)
**Related:** [`../safety-disclaimer.md`](../safety-disclaimer.md), `python/cam_creation_studio/safety/rules.py`

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

## 4. The result type

Recommended name: **`ExportPreflightResult`**.

Acceptable alternatives if repository vocabulary review prefers one:
`export_eligible`, `export_blocking`, `preflight_passed`, `dialect_compatible`,
`validation_complete`.

Documented target shape:

```python
@dataclass(frozen=True, slots=True)
class ExportPreflightResult:
    export_allowed: bool
    blocking_findings: tuple[Diagnostic, ...]
    advisory_findings: tuple[Diagnostic, ...]
    policy_version: str
    disclaimer: str
```

### Convention notes for whoever implements it

- `Diagnostic` already exists at `python/cam_creation_studio/models.py`
  (`severity`, `code`, `message`, `line`). Reuse it. Do not define a second
  diagnostic type.
- Diagnostic codes are centrally owned by
  `python/cam_creation_studio/gcode/validator/codes.py`. Any preflight code
  belongs there, following the CS-003 conventions.
- The package is frozen-dataclass-only (Ruling 6). No Pydantic.
- `models.py` currently uses `List[...]`; `tuple[...]` is the shape specified by
  the ruling. Reconcile against existing conventions at implementation time and
  record the choice.
- `disclaimer` should carry `safety.rules.DISCLAIMER` rather than a new string.

**No such type is created in this increment.** This section records the target so
a later increment does not have to relitigate it.

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
