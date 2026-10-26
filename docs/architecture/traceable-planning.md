# Traceable planning

**Order:** CS-PEP-001
**Status:** Experimental local boundary. Operational governed export is disabled.

Creation Studio owns the planning request, the plan record, verification, and
the governed-export check. It does not own manufacturing-intent admission,
instrument design, or physical-engineering thresholds. CAM Assist admission
is consumed through an experimental adapter. Luthier's Toolbox and Physical
Engineering Mesh are not imported.

This boundary does not establish acoustic validity and does not authorize
physical machining.

## Ownership

| Concern | Owner in this increment |
|---|---|
| `TraceablePlanningRequestV1`, `TraceablePlanV1`, review binding, export manifest | Creation Studio |
| Proposal, validation, and admission meaning | Not ratified here. Only experimental fixture profiles are parsed |
| Contour, pocket, and drill planning | Not this order. CS-017 remains unissued |
| Ordinary manual G-code | Existing `camstudio generate` path |
| Human approval | Not configured. A fixture review tests binding only |

## Workflow states

```text
imported package
  → strict parse
  → package-local resolution
  → exact-byte digest check
  → identity binding
  → local maturity and producer trust
  → declared manufacturing limits
  → candidate planning
  → motion checks, when explicit motion is supplied
  → review of the exact plan digest
  → operational export (disabled) or offline witness record
```

Candidate planning may be attempted before review. Admission to human review
is not plan approval. Governed export requires a review bound to the plan
digest that was actually checked. Human-authored jobs that carry no imported
artifact chain stay on the existing generator and preflight path. An imported
chain cannot be turned into that path by changing a label or `workflow_origin`.

## Schema profile

Studio contracts:

| Document | Version |
|---|---|
| Planning request | `creation-studio.traceable-planning-request/1` |
| Plan digest payload | `creation-studio.traceable-plan/1` |
| Export manifest | `creation-studio.traceable-export-manifest/1` |
| Review record | `creation-studio.plan-review/1` |

Upstream profiles pinned for offline fixtures only, not as canonical published
schemas:

| Role | Contract | Version | Maturity |
|---|---|---|---|
| proposal | `experimental.cam-assist.proposal` | `fixture-1` | experimental |
| validation | `experimental.cam-assist.validation` | `fixture-1` | experimental |
| admission | `experimental.cam-assist.admission` | `fixture-1` | experimental |
| geometry | `experimental.creation-studio.geometry` | `fixture-1` | experimental |
| subject | `experimental.creation-studio.subject` | `fixture-1` | experimental |

Unknown contract ids, versions, and extra fields are refused. `pin_status`,
`approved`, `advisory_allowed`, and `advisory_authority_granted` do not assign
maturity or approval. Maturity is assigned locally and is experimental.

## Digest rules

Structured fingerprints use canonical JSON: object keys sorted, no
insignificant whitespace, UTF-8, and no non-finite numbers. Tuples are encoded
as arrays. The plan digest and the strategy fingerprint exclude volatile
timestamps.

External artifacts are hashed as the exact stored bytes. A parsed document is
not written back out and then hashed in place of those bytes.

`strategy_fingerprint` on `ToolpathStrategy` includes ordered
`depth_levels_mm`. The traceable strategy fingerprint adds clearance and stock
allowance. A stored feed recommendation is attached to a toolpath only when
its id is selected explicitly.

The plan digest covers the request digest, artifact digests, strategy
fingerprint, tool diameter, allowance, stock id, frame, units, profile,
planner id and version, postprocessor id and version, local policy digest,
toolpath digest, and motion source. A review binds `plan_digest` and
`policy_digest`. Changing any of those inputs makes the previous review
inapplicable.

## Trust boundary

Checks run in this order:

1. Bounded JSON parse. Reject unknown fields, duplicate keys, missing fields,
   wrong types, blank identities, invalid timestamps, non-finite numbers, and
   unsupported operations.
2. Resolve references under the package root. Refuse absolute paths, `..`,
   remote references, symlinks, missing files, and unreadable files.
3. Compare SHA-256 of the captured bytes with the declared digest, then parse
   the supported profile.
4. Bind proposal, validation, admission, package, subject, geometry revision,
   frame, and units. A claimed current state other than `not_established`
   cannot be confirmed.
5. Assess the admission producer. A digest is not provenance. No operational
   publisher is configured. Offline mode accepts only
   `synthetic-fixture-producer`.
6. Run the supported manufacturing checks.
7. At export, re-read the snapshot and the review. Generation uses that same
   snapshot.

## Supported witness limits

The only supported demonstration shape is a closed rectangular contour in
millimetres, frame `stock-fixed-coupon-xy`, flat end mill, fixed orientation,
fixed radius, and explicit depth levels. Arcs, helical entries, compound
surfaces, and indexed setups are refused.

Implemented checks:

* cutter disk, grown by the declared positional tolerance, inside the
  axis-aligned removal rectangle for plunge and cut
* plunge and cut depth within the declared maximum and the explicit levels
* an engaging move changes XY or Z, not both. A ramp that starts above
  the stock is refused, as is a ramp that stays below it
* travel stays at or above the declared clearance; a retract may climb
  vertically and must finish at or above clearance, and it must not move in
  XY while it is still below that clearance
* profile, units, tool kind, and orientation

Not implemented: clamp collision beyond that rectangle, full machine
collision, structural safety, cutting force, and machine readiness. Unknown
positional tolerance is refused rather than treated as zero.

The contour planner is not implemented. The witness records
`UNSUPPORTED_CAPABILITY` and does not emit a candidate program. Explicit
linear motion used by tests is labeled `explicit_linear_motion`. It is not
planner output. Any program the offline gate renders is passed through
`cam_creation_studio.gcode.generator` and marked
`EXPERIMENTAL — NOT FOR MACHINING`.

## Reason codes

```text
SCHEMA_INVALID
UNSUPPORTED_VERSION
REFERENCE_UNRESOLVED
DIGEST_MISMATCH
PROPOSAL_BINDING_MISMATCH
GEOMETRY_REVISION_MISMATCH
SUBJECT_MISMATCH
PACKAGE_MISMATCH
FRAME_MISMATCH
UNITS_MISMATCH
UNTRUSTED_ADMISSION
EXPERIMENTAL_ONLY
UNSUPPORTED_CAPABILITY
REMOVAL_BOUND_EXCEEDED
DEPTH_LIMIT_EXCEEDED
CLEARANCE_VIOLATION
PROFILE_UNSUPPORTED
PLAN_CHANGED
REVIEW_REQUIRED
PROVENANCE_IMMUTABLE
CURRENT_STATE_UNAVAILABLE
POLICY_UNSUPPORTED
SNAPSHOT_CHANGED
```

Input and resolution failures return one of these refusals. Programming
defects raise `TraceabilityDefect` and are not reported as a successful
verification.
