# CS-018 results

Recorded 2026-10-27 (America/Chicago). No material was cut. Nothing was
merged or deployed. The program text below is experimental fixture output.

## Repository

| Item | Value |
|---|---|
| URL | `https://github.com/HanzoRazer/CAM-Creation-Studio` |
| Base branch | `main` |
| Base SHA | `416a466ea589ef29f92bbe2e74ce625f3f2b7443` |
| Requested branch name | `cs-018-generated-plan-identity` |
| Working branch | `cursor/cs-018-generated-plan-identity-39ad` |
| Implementation | `0cbfb9db8ece646d7896e629cc629fe08f6e7d67` |
| Pull request | #38, draft, not merged |
| Open pull requests at intake | none |

`eeb0ed0`, `08879bd`, and `753b2cb` are ancestors of this base. The
output-overlap, symlink, partial-publication, unreadable-review,
overflowing-number, and sequence-test patches were not reissued.

Python 3.12. Package version `0.1.0`. Commands were run from `python/`
unless noted. `python3 -m pip install -e '.[dev]'` installed `jsonschema`
4.26.0 for the Draft 2020-12 schema checks.

This machine, before the identity edits and before `jsonschema` was
installed: `python3 -m pytest -q --tb=line` reported `1178 passed, 21 skipped`
in 5.01s. The historical `1185 passed, 14 skipped` figure was not reused.

## What changed

Validated rectangle coordinates that are numerically zero become positive
floating-point zero before extrema, undirected edge matching, and generated
poses. A tiny nonzero stays nonzero. Captured source bytes are not rewritten.

`derive_rectangular_state` rebuilds the selected definition, that
definition's binding, geometry ids, recommendation, feeds, tool, material,
canonical plan, and digest from the verified request and the captured
planner-input and operation-plan bytes. `build_generated_candidate` is the
only constructor that assigns the generation seal. `replan_matches` compares
the candidate with that derivation. Candidate claims are not digest inputs.

`cam_creation_studio.traceability.service` was not edited. The shared export
gate already calls `replan_matches` before review binding and rendering, and
`export_planned_witness` already clears a stale program and manifest on
refusal. `DerivedRectangularState` is private in `planning.py`.
`traceability/models.py` was not given a second motion record.

Planner version is `2`. Planner id remains
`creation-studio.rectangle-centerline`. The local policy digest includes the
live rectangular version and the validation sentence. Its measured value on
this tree is
`d30d865e36586e3995b651caffe2dc18858296755e95a4c811d6ab246002fd88`.

## Negative control on `416a466`

The new test modules were copied onto a detached worktree of the base and
run before this correction was present:

```text
cd /tmp/cs018-base/python
python3 -m pytest tests/test_rectangular_identity.py tests/test_generated_candidate_identity.py --tb=line -q
```

`19 failed, 9 passed`. The failures that show the two defects:

* `test_two_edge_orders_share_positive_zero_poses` and the 24×16 matrix
  failed because `math.copysign(1.0, -0.0)` was `-1.0` on the plunge start
  for edge order `(0, 1, 2, 3)`. The oracle requires positive zero.
* Tool id, diameter, flutes, material id, binding id, and geometry ids, each
  replaced and then given a digest recomputed from that claim, left
  `replan_matches` returning `None`.
* `test_self_consistent_false_tool_and_material_still_refuses` and
  `test_identity_refusal_clears_a_previous_program` rendered a program.
  `program_text` began with `EXPERIMENTAL — NOT FOR MACHINING` and
  `refusal` was `None`, with a fixture review of the forged digest.
* A false cut or plunge feed, and a catalog chipload change, were already
  `PLAN_CHANGED` on the base, with the detail `regenerated rectangular plan
  does not match the candidate`. The base used the candidate feed and
  recommendation as expansion inputs. A false definition id or
  recommendation id therefore came back `UNSUPPORTED_CAPABILITY` from that
  expansion, not from an independent field comparison.
* `test_version_1_review_does_not_authorize_version_2` saw the same policy
  digest (`e666412c7a60d49d1c00f5c7b3ffced3b5825ff0c366e095baf4ede96c2d5320`)
  before and after `limits.PLANNER_VERSION` was changed. The base copied the
  version into policy at import.
* `derive_rectangular_state` does not exist on the base, so the
  reconstruction test raised `ImportError` and the snapshot spy could not
  be installed. The merged toctou tests already refuse `SNAPSHOT_CHANGED`
  before expansion. After this correction the same byte change leaves
  `derive_rectangular_state` uncalled.

Preservation tests (tiny nonzero, gap refusal, raw-byte SHA-256, CS-016
fingerprints, explicit-motion `unavailable`, verify-only) passed on the
base as well as after the correction.

## Commands after the correction

```text
cd python
python3 -m pip install -e '.[dev]'
python3 -m pytest tests/test_rectangular_identity.py tests/test_generated_candidate_identity.py tests/test_rectangular_contour_planner.py tests/test_planned_witness.py tests/test_traceable_review_regressions.py -q --tb=short
```

`139 passed` in 2.18s.

```text
cd python
python3 -m pytest -q --tb=line
```

`1213 passed, 14 skipped` in 5.50s. The seven Draft 2020-12 schema tests
that were skipped before `jsonschema` was installed now run. `git diff
--check` reported no whitespace errors.

## Witness

Package built with `tests/support/rectangle_planned.write_planned_package`
at `/tmp/cs018-witness/package`. The rectangle is the inset coupon from
`(20, 15)` to `(60, 35)`, not the origin rectangle used by the zero-sign
unit tests. Fixture review bytes came from
`tests/support/fixture_review.py`.

```text
python3 tools/run_traceable_planning_witness.py --package /tmp/cs018-witness/package --destination /tmp/cs018-witness/verify --mode verify --case rectangle
python3 tools/run_traceable_planning_witness.py --package /tmp/cs018-witness/package --destination /tmp/cs018-witness/prepare --mode prepare --case rectangle
python3 tools/run_traceable_planning_witness.py --package /tmp/cs018-witness/package --destination /tmp/cs018-witness/export --mode export --review /tmp/cs018-witness/review.json --case rectangle
```

| Step | Exit | Result |
|---|---|---|
| verify | 1 | `UNSUPPORTED_CAPABILITY`. No program. Detail: verification-only witness does not run the rectangular planner |
| prepare | 1 | `candidate_ready`, `export_status=blocked`, `REVIEW_REQUIRED`. No program |
| export | 0 | `program_written=true`. `human_approval` false. `operational_export` false |

| Item | Value |
|---|---|
| Planner version on the candidate and manifest | `2` |
| Motion source | `rectangular_centerline_planner` |
| Toolpath version | `camstudio_toolpath_v1` |
| Plan digest | `0343f2045da08d6b9dac3bf06a4d02b35be071f39a93cb39b9b49632cdf06e13` |
| Program SHA-256 | `222d06b0a231b730f17f4d57711356f1fe2e07a7efee58f78e7d4aab3d04b0a6` |
| Manifest `program_sha256` | the same digest |
| Banner | `EXPERIMENTAL — NOT FOR MACHINING` |
| Review authority | `fixture_binding_only` |

The program SHA-256 equals the experimental program recorded for the same
coupon in `docs/implementation/CS-017-results.md`. It was measured again
here. The plan digest does not equal the CS-017 digest
`01b2e014a4d163e82713eda1594e1f5800874981154acbadda36973ac2de8a81`, because
planner version `2` and the new policy digest are inside the generated
digest. G-code bytes for this coupon did not change.

## Deferred

No feed ceiling was added. A finite feed of `1e300` mm/min can still pass
the numeric feed check. Whether that needs a physical limit is a separate
policy question.

This correction does not add a canonical upstream validator, publisher
trust, human-review authority, operational export, or a machining
authorization. In-process agreement between a candidate and bytes captured
in this process is not a claim that the process is sealed against arbitrary
code execution.

## PR 38 review corrections on October 28

Reviewed at `eca79a9107603fb42b766ea0a8b6bbc51754c846` in an isolated
Creation Studio worktree. The structured digest domain (contract version,
motion source, planner identity, local policy, and canonical payload), the
signed-zero boundary, and the fixture-only authority model were already
implemented; those review concerns did not require a redesign.

Confirmed and corrected:

* Captured reference aliases were accepted when their file bytes matched.
  Replacing an operation-plan or planner-input reference could change emitted
  provenance without changing the reconstructed digest. Construction and
  revalidation now compare those references with the supported input path
  and the parsed planner-input document.
* `candidate.plan = None`, a string, or a dictionary raised during projection
  or serialization. The shared gate now reconstructs generated candidates
  before projecting their plans, and a wrong model type is `PLAN_CHANGED`.
* Historical digest/policy refusals now explain the required action:
  re-prepare under current planner/policy and create a new fixture-binding
  review. This changes no authority, schema version, or planner version.
* The deferred feed range is now named `CS018-DEFERRED-FEED-RANGE` and has
  explicit extreme-cut/plunge regression cases proving labeled offline-only
  output and operational refusal. No physical feed limit was selected.

The new file `python/tests/test_cs018_review_regressions.py` contains nine
cases. Before the fixes, six failed for the intended reasons: two accepted
reference substitutions, three plan-type exceptions, and one missing
migration instruction. The remaining cases confirm already supported digest
domain separation and explicitly deferred feed-range behavior.

Verification on Python 3.12 with pytest 8.4.2:

```text
cd python
python -m pytest -q --tb=line
1222 passed, 14 skipped
```

`git diff --check` is clean. The skips are the existing scaffolder cases.

The initial baseline run with pytest 9.2.0 had two unrelated failures in
`test_cs008r_closure.py`: nested `pytest.approx()` expectations are rejected.
The development dependency now temporarily requires `pytest>=7,<9.2` until
those existing assertions are migrated. Neither geometry runtime nor the
frozen importer was changed.

No merge, deployment, trust activation, human machining approval, or
operational export was performed in this review increment.
