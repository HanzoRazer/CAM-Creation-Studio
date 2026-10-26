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
  removal rectangle over the whole of every plunge and cut
* removal rectangle inside the stock footprint
* engaging depth within the declared maximum and the explicit depth levels
* travel at or above clearance; retract must finish there and must not dive
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

## PR 33 review corrections on October 26

Reviewed and patched from PR head
`9b731c086f7fcbd6867f69ddc5c4ff53e4544674` on the existing PR branch.
The original results above are historical; this verification uses Python
3.12 and the repository dev dependencies plus JSON Schema validation.

The cited origin concern was a contract scope ambiguity: schema validity and
policy admissibility can legitimately differ, but this particular request
contract always requires an imported artifact chain. Its published origin is
now explicitly `imported`; the parser keeps its defensive relabel refusal.

The other cited concerns are addressed by a policy-bound `1e-9` mm absolute
depth identity tolerance (hard removal limits are not relaxed), namespace and
artifact-shaped classification, raw-byte digest regression cases, and
explicit `TraceabilityDefect` checks instead of production assertions.

Additional defects corrected:

* Published nested request and manifest objects were closed without declaring
  their required properties, rejecting valid payloads. Complete definitions
  now run through actual Draft 2020-12 schema validators in tests.
* Discontinuous motion could pass segment checks while posting connected
  different endpoints. Continuity, finite poses, safe initial/final poses,
  vertical plunge/retract, and level-cut checks now cover that gap.
* Three-decimal G-code rounding could invalidate checked bounds. Posted
  coordinates are checked too; rounded-zero or non-finite feeds are refused.
* Duplicate generate-document keys could erase provenance before
  classification. The generate entry now uses strict bounded JSON parsing.
  (Narrowed in the merge-readiness corrections below.)
* Strategy identity and frame name were absent from request fingerprints.
  Both now invalidate dependent plan reviews.
* Large numeric/nested JSON could raise instead of refusing; those input
  limits now produce structured refusals. Artifact reads stop at the size
  limit instead of loading an unbounded file first.
* Offline writes now preserve exact UTF-8 program bytes, check the banner and
  digest, and record refusal results. Fixture Git attributes preserve their
  hashed bytes on Windows checkout.

Verification after the code changes:

```text
cd python
python -m pytest -q tests/test_traceable_planning.py tests/test_traceable_review_regressions.py --tb=short
71 passed
python -m pytest -q --tb=line
1105 passed, 14 skipped
```

The 14 skips are the pre-existing scaffolder integration tests. The new
regression file contributes 31 tests. The original branch passed
`1074 passed, 14 skipped` in this environment before these fixes. An explicit
`python -O` check confirmed the defect guard remains active under optimization.
`git diff --check` is clean. No machining, deployment, or merge was performed.

| Refusal | Trigger | Offline artifacts |
| --- | --- | --- |
| `SCHEMA_INVALID` | Malformed request or unsupported numeric/nesting limits | Witness `result.json`; no program |
| `DIGEST_MISMATCH` | Changed bytes, including newline/encoding/whitespace | Witness `result.json`; no program |
| `PROVENANCE_IMMUTABLE` | Relabeled imported chain | CLI refusal report or witness result; no new program |
| `UNSUPPORTED_CAPABILITY` | Missing planner, discontinuous motion, or unsupported entry | Result record; no program |
| `REMOVAL_BOUND_EXCEEDED` | Original or posted cutter envelope escapes the region | Offline result; no program |
| `DEPTH_LIMIT_EXCEEDED` | Hard depth maximum or discrete level check fails | Offline result; no program |
| `EXPERIMENTAL_ONLY` | Fixture requested as operational export | Offline result or CLI refusal; no new program |

Offline-writer results require invoking `write_offline_export`; the pure
evaluation API does not write files. The ordinary generate CLI preserves its
existing behavior of leaving a pre-existing output untouched on refusal.
These are input/workflow controls, not a sandbox against arbitrary Python
code or an ability to recover provenance that a third party entirely deletes.
Operational governed export, trusted human review, and contour planning remain
unavailable.

## Merge-readiness corrections on October 26

Reviewed at PR head `dfd8b992a71a4d46757c90bee473c97b5586b9c2`. Each defect was
reproduced with a probe before it was fixed, and each new test fails on that head.

* **Cuts below clearance were unchecked in XY.** The swept-volume check only
  considered the part of a segment at or below the stock top, so a level cut
  at Z0.5 could reach X500 Y500 on an 80 x 50 coupon with 5 mm clearance and
  still be posted. Containment now covers both endpoints of every plunge and
  cut. Each segment is straight and the rectangle is convex, so the endpoints
  bound the whole segment.
* **The removal region was never checked against the stock.** `stock.x_mm`
  and `stock.y_mm` were parsed but unused. The removal rectangle must now lie
  within the stock footprint.
* **Every existing strategy fingerprint changed.** The payload always carried
  `depth_levels_mm: []` and turned integers into floats, so every stored CS-016
  plan would read as stale. Empty depth levels are now omitted and values are
  not coerced. Tests pin three fingerprints recorded on `main` at `a2f445e`.
* **Manual `camstudio generate` regressed.** Every job went through the
  governed-package limits, so jobs over 256 KiB, jobs with duplicate keys, and
  jobs with NaN were refused. An ordinary job now falls back to the
  pre-CS-PEP-001 parser. Governed documents keep strict parsing, and a
  duplicated classifying key still refuses, so the provenance-erasure defence
  is kept.
* The schema regression tests skip individually when the optional
  `jsonschema` dev dependency is absent. Before, the whole file failed to
  collect.

```text
cd python
python -m pytest -q --tb=line
1117 passed, 14 skipped
```

Witness exits are unchanged: consistent `UNSUPPORTED_CAPABILITY`, depth
`DEPTH_LIMIT_EXCEEDED`, geometry `GEOMETRY_REVISION_MISMATCH`, admission
`PROPOSAL_BINDING_MISMATCH`. None writes a program.

Open and not addressed here:

* `CS-PEP-` is not registered in the ledger's identifier namespaces. That needs
  an owner ruling.
* Origin classification matches only the exact string `imported`.
