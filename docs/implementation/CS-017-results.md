# CS-017 results

Recorded 2026-10-26 (America/Chicago). No material was cut. Nothing was
merged or deployed. The program text below is experimental fixture output.

## Repository

| Item | Value |
|---|---|
| URL | `https://github.com/HanzoRazer/CAM-Creation-Studio` |
| Base branch | `main` |
| Base SHA | `374fa5832e571cebb470c5dc2e57f43b71e71226` |
| Requested branch name | `cs-017-rectangular-contour-witness` |
| Working branch | `cursor/cs-017-rectangular-contour-witness-39ad` |
| Verified implementation | `f96a9dd29bccb8d5b49cc86b98cd1760d8b3e330` |
| Draft record | `d4f2af60ce45e7bdb02fbfeed482bf03fbc76634` |
| Failure-path implementation | `08879bda05ccda9137aed5ba89e86249d14f1c65` |
| Pull request | #36, not merged |

Stage 0 on this machine, before the planner edits: `python3 -m pytest -q --tb=line`
from `python/` reported `1110 passed, 21 skipped`. That is the count for this
environment. The historical `1117 passed, 14 skipped` figure was not reused.
Open pull requests at intake: none. No remote CS-017 branch was present.
Closed #34 was not stacked and its motion predicates were not reapplied.

Python 3.12.3. Package version `0.1.0`. The tree already imported
`cam_creation_studio`; the suite was run from `python/` against that tree.

## Commands

```text
cd python
python3 -m pytest tests/test_rectangular_contour_planner.py tests/test_planned_witness.py tests/test_traceable_planning.py tests/test_traceable_review_regressions.py -q --tb=short
```

`125 passed, 7 skipped`.

```text
cd python
python3 -m pytest -q --tb=line
```

`1159 passed, 21 skipped in 4.00s`.

`git diff --check` produced no output.

## Witness CLI

From the repository root. Verify is the default and does not read planner
inputs.

```text
python3 tools/run_traceable_planning_witness.py \
  --package python/tests/fixtures/traceable_planning/rectangle_planned \
  --destination <verify-dir> \
  --mode verify \
  --case rectangle_planned
```

Exit 1. `reason_codes` is `UNSUPPORTED_CAPABILITY`. `program_written` is
false. No candidate file is written.

```text
python3 tools/run_traceable_planning_witness.py \
  --package python/tests/fixtures/traceable_planning/rectangle_planned \
  --destination <prepare-dir> \
  --mode prepare \
  --case rectangle_planned
```

Exit 1. `planning_status=candidate_ready`, `export_status=blocked`,
`reason_codes=["REVIEW_REQUIRED"]`. `candidate_plan.json`, `preview.json`,
and `result.json` are written. No program is written.
`program_exported` and `human_approval` on the candidate are false.

```text
python3 tools/run_traceable_planning_witness.py \
  --package python/tests/fixtures/traceable_planning/rectangle_planned \
  --destination <export-dir> \
  --mode export \
  --review <fixture-review.json> \
  --case rectangle_planned
```

Exit 0 only when the review binds the prepared plan digest and the local
policy. This run wrote `program.gcode` and `manifest.json`.

| Item | Value |
|---|---|
| Plan digest | `01b2e014a4d163e82713eda1594e1f5800874981154acbadda36973ac2de8a81` |
| Program SHA-256 | `222d06b0a231b730f17f4d57711356f1fe2e07a7efee58f78e7d4aab3d04b0a6` |
| Manifest `program_sha256` | the same digest |
| Planner | `creation-studio.rectangle-centerline` version `1` |
| Motion source | `rectangular_centerline_planner` |
| Manifest contract | `creation-studio.traceable-export-manifest/2` |

The program begins `(EXPERIMENTAL — NOT FOR MACHINING)`, rapids to the
clearance pose `(20, 15, 5)`, plunges to `Z-1` at `F300`, cuts the
rectangle at `F800`, and retracts. The candidate's embedded toolpath
version remains `camstudio_toolpath_v1`.

`--mode export` without `--review`, and `--mode prepare` with `--review`,
exit 2. There is no operational, approve, or force switch.

## What this increment does

The planner turns one explicit Z0 rectangle into two paths and twelve
linear motions for depths 1 mm and 2 mm. Horizontal cutting distance is
240 mm. The canonical plan uses the operation plan's definition, binding,
and geometry ids. The 1/4 inch catalog tool (`endmill_1_4`, 6.35 mm) and
`hardwood` are the binding. A stored feed recommendation is present and
not selected. Independent bounds checks accept the plan and refuse a
corrupted endpoint. Preview is a lossy projection of that plan. A separate
fixture review allows one labeled offline program.

## Failure-path revision

Recorded 2026-10-27 (America/Chicago) on parent
`d4f2af60ce45e7bdb02fbfeed482bf03fbc76634`.

Witness outputs are refused when a destination or output path is a symlink,
or when an output resolves to a captured input: the request, an upstream
artifact, `planner-inputs.json`, or the operation-plan reference. That
refusal happens before any write or delete, so an operation plan stored at
`out/program.gcode` is not removed by stale-output cleanup, and a
`program.gcode` symlink is not followed. Program and manifest bytes are
staged and published together. If manifest publication fails, the program
is removed and `result.json` records the failure, including when the
previous record was `REVIEW_REQUIRED` or a successful export. An unreadable
`--review` file uses that same failure result, exits 1, and clears the
previous program. Integers that cannot be represented as finite floats,
including a feed of `10**1000`, are refused with `SCHEMA_INVALID` at
planner-input intake and at the same conversions in the planner.

The rectangle permutation test compares the full ordered motion sequence,
after edge permutation and endpoint reversal, with the handwritten oracle.

```text
cd python
python3 -m pytest tests/test_rectangular_contour_planner.py tests/test_planned_witness.py tests/test_traceable_planning.py tests/test_traceable_review_regressions.py -q --tb=line
```

`133 passed, 7 skipped`.

```text
cd python
python3 -m pytest -q --tb=line
```

`1167 passed, 21 skipped in 5.06s`.

`git diff --check` produced no output. The plan digest and program SHA-256
above are unchanged. The shared review gate, the operational-export
refusal, and the bounds checker are unchanged.

## Independent review corrections on October 27

Reviewed at `964a8dee5d388329a92c9a3df7fc1773cff89622`. Each item below was
reproduced with a probe. Each new test fails on that head.

* **The new tests did not run on Windows.** `tests.support` resolves only
  when `tests` is a namespace package. Any installed regular `tests` package
  shadows it, and collection fails. The imports now use `support`, the same
  sibling-import idiom as `from test_traceable_planning import ...`.
* **Fixture builders wrote CRLF on Windows.** `write_text` translated
  newlines, so the rebuilt package did not match the committed LF bytes and a
  test reported `DIGEST_MISMATCH`. The writers in
  `traceability/synthetic.py` and `tests/support/rectangle_planned.py` now
  pin `newline="\n"`, and the test writes the bytes it hashes.
* **A review file inside the destination was replaced or deleted.** With
  `--review out/manifest.json`, `out/program.gcode` or `out/result.json`, a
  successful export overwrote the review. With `out/candidate_plan.json` it
  was deleted. A review path that is, or links to, a witness output is now
  refused before anything is read, written or deleted.
* **A failed invalidation left a stale success record.** When every
  publication failed after an earlier success, the program and manifest were
  removed but `result.json` still said `program_written: true`. The old
  record is now removed before the new one is written.
* **Malformed operation-plan numbers raised instead of refusing.**
  - An edge coordinate given as a 1001-digit integer, a string or a bool
    raised `OverflowError` or `TypeError`, or was accepted as Z0. These now
    refuse with `UNSUPPORTED_CAPABILITY`.
  - A 1001-digit `target_depth_mm` or `stock_allowance_mm` escaped
    `decode_operation_plan`. It now refuses with `SCHEMA_INVALID`.
* `_rectangle_from_plan` now catches `WorkspaceError`, not `Exception`.
* Witness CLI output now includes `mode`.

```text
cd python
python -m pytest -q --tb=line
1185 passed, 14 skipped
```

Open, not changed here:

* Feeds have no upper bound. A planned cut feed of `1e300` produces an
  experimental program with a 300-digit `F` word. Choosing a limit is
  manufacturing policy, and that needs an owner decision.
* `replan_matches` re-derives the motions, but not the candidate's tool or
  material metadata. A forged in-process candidate can carry wrong metadata.
  It cannot be reached from package bytes.
* A `-0.0` coordinate changes the candidate JSON and digest depending on edge
  order. The G-code is identical.

## What remains

Canonical upstream admission and trust, a governed review of real
artifacts, offset and pocket and drill planning, and operational export.
This order does not lift real-tonewood evidence requirements in other
repositories and does not authorize physical machining.
