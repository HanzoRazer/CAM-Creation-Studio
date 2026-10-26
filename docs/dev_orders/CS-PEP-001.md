# CS-PEP-001 — Traceable planning boundary

```text
Repository:                CAM-Creation-Studio
Repository Root:           HanzoRazer/CAM-Creation-Studio
Repository Branch:         cursor/cs-pep-001-traceable-planning-eaf7
Parent Artifact:           docs/TOOLPATH_CORE.md
Authority:                 CS-016 closed the motion contract and left planners
                           unissued. Export preflight remains the ordinary
                           program gate (docs/architecture/EXPORT_PREFLIGHT_SEMANTICS.md).
                           Cross-repository policy is docs/GOVERNANCE/CROSS_REPOSITORY_BOUNDARIES.md.
Generated:                 2026-10-25
Cross Repository Deps:     None imported. Experimental fixture profiles only.
```

## Stage 0 reconciliation

Verified before implementation, on 2026-10-25:

| Fact | Value |
|---|---|
| Repository | `https://github.com/HanzoRazer/CAM-Creation-Studio` |
| Default branch | `main` |
| Base SHA | `a2f445eebb169ca2ef00c8ba5469914a12a5352a` |
| Working tree | clean `main`, tracking `origin/main` |
| Open pull requests | none (`gh pr list --state open`) |
| Python package | `python/cam_creation_studio`, `python/pyproject.toml`, no runtime dependencies |
| CI workflow | none in the tree |
| AGENTS.md | not present |
| Contour planner | absent. `docs/TOOLPATH_CORE.md` forbids `plan_contour` in the toolpath package. CS-017 is unissued |
| Postprocessor | `cam_creation_studio.gcode.generator` posts educational G-code from moves. It does not consume a `ToolpathPlan` |
| Preview | `toolpath_to_preview` exists and is named by the witness when no plan exists |
| Upstream schemas | no ratified CAM Assist, Toolbox, or Physical Engineering Mesh contracts in this tree |
| Trust anchor | none |
| Human-review verifier | none |

Commands used: `git remote -v`, `git status -sb`, `git rev-parse HEAD`, `git branch -r`, `gh pr list --state open`.

### CS-016 prerequisites

On this base, `strategy_fingerprint` omitted depth levels, and `build_toolpath_plan` copied any stored recommendation. Both are corrected here, with regression tests. The recommendation system itself is unchanged.

### Path mapping

| Proposed destination | Actual path |
|---|---|
| `docs/dev-orders/CS-PEP-001.md` | `docs/dev_orders/CS-PEP-001.md` |
| `docs/architecture/traceable-planning.md` | same |
| request / plan / manifest schemas | `schemas/traceable_*_v1.schema.json` |
| `src/creation_studio/traceability/` | `python/cam_creation_studio/traceability/` |
| export integration | `python/cam_creation_studio/cli/commands/generate.py` calls `traceability.service` |
| strategy fingerprint | `python/cam_creation_studio/toolpath/fingerprint.py` |
| recommendation selection | `python/cam_creation_studio/toolpath/builders.py` |
| tests | `python/tests/test_traceable_planning.py` and existing toolpath tests |
| fixtures | `python/tests/fixtures/traceable_planning/` |
| witness CLI | `tools/run_traceable_planning_witness.py` |
| results | `docs/implementation/CS-PEP-001-results.md` |

No parallel package was added. No sibling checkout is imported.

## Objective

Bind imported manufacturing intent to an exact plan and to the export gate for one synthetic rectangular contour. The chain keeps subject identity, geometry revision, removal limits, artifact digests, and review requirements.

Success here is refusal and traceability. It is not a machining authorization. The contour planner is blocked, so the offline witness does not emit a candidate program. Explicit linear motion can still exercise the manufacturing checker and the existing generator; that motion is labeled `explicit_linear_motion` and is not planner output.

## Decisions carried into the code

1. Python is the only planning implementation. The browser UI is untouched.
2. Upstream profiles are experimental fixture pins. No canonical upstream version is invented.
3. Creation Studio does not re-evaluate physical evidence sufficiency. It checks that an admission binds the proposal, subject, geometry revision, and package, and it refuses to treat admission as plan approval.
4. Compatibility, maturity, and trust are local. `pin_status`, `approved`, and advisory flags cannot promote a fixture.
5. There is no CLI switch that makes a fixture operational.
6. Governed export requires a review of the exact plan digest. Operational export stays disabled.
7. Human-authored jobs without imported markers keep `camstudio generate`. Relabeling an imported document does not.
8. No physical-engineering threshold, soundboard rule, machine controller, or automatic execution is introduced.

The closed reason vocabulary is recorded in `docs/architecture/traceable-planning.md`.
