# CS-PEP-001 results

Recorded 2026-10-25 (America/Chicago). No material was cut. Nothing was merged
or deployed.

## Repository

| Item | Value |
|---|---|
| URL | `https://github.com/HanzoRazer/CAM-Creation-Studio` |
| Base branch | `main` |
| Base SHA | `a2f445eebb169ca2ef00c8ba5469914a12a5352a` |
| Working branch | `cursor/cs-pep-001-traceable-planning-eaf7` |
| Verified implementation | `e69569e7ed4502e23e5454e2a1e41c8a3f0c1e9c` |
| Branch head | the commit that records this line, directly above that implementation commit |

Stage 0 commands and the path mapping are in
[`../dev_orders/CS-PEP-001.md`](../dev_orders/CS-PEP-001.md).

## What is implemented

* Studio-owned request, plan-digest, review, and export-manifest contracts.
* Strict parsing, package-local resolution, exact-byte digests, and identity
  binding.
* A local experimental compatibility policy. No canonical upstream version is
  claimed.
* Producer trust that accepts only the pinned synthetic producer, and only
  for offline verification.
* Declared-limit checks and conservative rectangular swept-volume checks.
* Governed `camstudio generate` refusal through the same service the witness
  uses. Ordinary manual jobs still generate.
* Explicit `recommendation_id` selection, and `depth_levels_mm` inside
  `strategy_fingerprint`.
* Offline rendering of already-supplied linear motion through
  `gcode.generator.program_to_text`, marked
  `EXPERIMENTAL — NOT FOR MACHINING`, and only after the shared gate passes.

## What stays experimental or blocked

| Capability | State |
|---|---|
| Fixture profiles `fixture-1` | Experimental. Not operational contracts |
| Operational trust | Blocked. No publisher or review anchor exists |
| Operational governed export | Disabled (`EXPERIMENTAL_ONLY` / `UNTRUSTED_ADMISSION`) |
| Human approval | Blocked. Fixture reviews test binding only |
| Contour planner | Blocked. CS-017 is unissued. The witness does not invent a toolpath |
| Current-state / supersession authority | Blocked. Anything other than `not_established` is refused |
| Acoustic validity, machine readiness, physical machining | Not claimed |

The witness for a consistent coupon verifies the import chain, then refuses
planning with `UNSUPPORTED_CAPABILITY`. Depth, geometry-revision, and
substituted-admission cases refuse earlier and write no program. Those runs
use separate destination directories.

Explicit linear motion in unit tests is not described as planner output.
`motion_source` is `explicit_linear_motion` and `planner_id` is `unavailable`.

## Checks

From `python/`, after installing pytest into the local environment:

```text
python3 -m pytest -q --tb=line
853 passed, 24 skipped in 0.92s
```

The 24 skips are pre-existing (scaffold and optional DXF cases), not new
waivers. Focused file:

```text
python3 -m pytest tests/test_traceable_planning.py tests/test_toolpath_ids.py tests/test_toolpath_lineage.py tests/test_cli_generate.py -q
```

passed before the committed-fixture assertion was added; the full run above
includes that assertion (`40` tests in `test_traceable_planning.py`).

Witness CLI, 2026-10-25, exit status 1 in every case, only `result.json`
written:

| Package | Reason | Program |
|---|---|---|
| `coupon_consistent` | `UNSUPPORTED_CAPABILITY` — contour planner is not implemented; CS-017 is unissued | no |
| `coupon_depth` | `DEPTH_LIMIT_EXCEEDED` — depth level 4.0 mm exceeds declared removal limit 3.0 mm | no |
| `coupon_geometry` | `GEOMETRY_REVISION_MISMATCH` | no |
| `coupon_admission` | `PROPOSAL_BINDING_MISMATCH` — admission names a different proposal | no |

Command:

```text
python3 tools/run_traceable_planning_witness.py \
  --package python/tests/fixtures/traceable_planning/<case> \
  --destination <separate-directory> \
  --case <case>
```

There is no flag that marks a fixture operational.

## Manufacturing checks that actually run

For the synthetic coupon only:

* cutter disk of radius plus declared positional tolerance inside the
  removal rectangle on plunge and cut
* engaging depth within the declared maximum and the explicit depth levels
* travel at or above clearance
* a retract may climb vertically and must finish at or above clearance; it
  must not descend, and it must not move in XY while still below clearance
* an engaging move may change XY or Z, not both, including an entry that
  starts above the stock
* flat end mill, fixed orientation, millimetres, frame
  `stock-fixed-coupon-xy`, profile `synthetic-router-mm`

Not run: clamp collision beyond that rectangle, structural checks, cutting
force, machine readiness, or a generated contour.

The envelope test uses an independent disk test in
`python/tests/test_traceable_planning.py`. A centerline that stays inside the
removal rectangle while the cutter disk does not is
`REMOVAL_BOUND_EXCEEDED`. Tampered bytes are `DIGEST_MISMATCH`. Bytes changed
after a captured snapshot are `SNAPSHOT_CHANGED`. Removing either comparison
fails the corresponding test.

## Next dependency

The smallest next dependency is a real contour planner (the unissued CS-017
contract) or a ratified upstream admission schema plus a trusted publisher.
Until one of those exists, governed export of a planned program stays blocked.
This order does not start that planner.

## Follow-up, 2026-10-26 (America/Chicago)

Branch `cursor/cs-pep-001-traceable-planning-39ad` continues the draft above.
A plunge that changes XY while descending was accepted when it started above
the stock, because the ramp check required both endpoints to be below Z=0.
A retract could also move in XY while its start was still below clearance.
Both are refused now. The contour planner is still absent, so the witness
still does not write a program.

Re-ran from `python/` on this tree:

```text
python3 -m pytest -q --tb=line
1074 passed, 14 skipped in 4.50s
```

The 14 skips are the pre-existing scaffold-tool cases. Optional DXF tests
ran in this environment, which is why this count is higher than the
2026-10-25 record of 853 passed and 24 skipped.

Witness CLI, separate directories, exit 1, only `result.json`:

| Package | Reason | Program |
|---|---|---|
| `coupon_consistent` | `UNSUPPORTED_CAPABILITY` — contour planner is not implemented; CS-017 is unissued | no |
| `coupon_depth` | `DEPTH_LIMIT_EXCEEDED` — depth level 4.0 mm exceeds declared removal limit 3.0 mm | no |
| `coupon_geometry` | `GEOMETRY_REVISION_MISMATCH` | no |
| `coupon_admission` | `PROPOSAL_BINDING_MISMATCH` — admission names a different proposal | no |

Disabling the checks, then restoring them:

* With the SHA-256 comparison forced off, `test_changed_bytes_and_reserialization_do_not_match` failed (`PROPOSAL_BINDING_MISMATCH` instead of `DIGEST_MISMATCH`).
* With the cutter-disk test forced true, `test_centerline_inside_envelope_outside_is_refused` failed (`REVIEW_REQUIRED` instead of `REMOVAL_BOUND_EXCEEDED`).

Those edits were not kept.
