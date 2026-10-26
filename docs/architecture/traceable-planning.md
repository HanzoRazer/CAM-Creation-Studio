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

The planning-request schema is for `workflow_origin: imported` only. It is
not the ordinary manual-job schema. The parser retains the explicit
`PROVENANCE_IMMUTABLE` refusal when a caller tries to relabel this chain.
JSON Schema checks structure; relational identity and manufacturing policy
remain additional checks. Schema-valid is not admission or export approval.

The reserved namespaces `traceability`, `traceable_planning`, and
`traceable_plan`, and the field `upstream_artifacts`, classify a generate
document as governed at the root or inside `config`/`job`, even if malformed.
Artifact-shaped `admission` objects and traceable-request contract IDs also
classify as governed. A generic operator note named `admission` does not.
Duplicate keys are rejected before classification so a second origin value
cannot erase the first. An ordinary manual job that fails only the bounded
parser's limits (size, duplicate keys, non-finite numbers) is parsed as it was
before this order. That fallback is refused when the leniently parsed document
looks governed or when any classifying key (`workflow_origin`, `config`, `job`,
`admission`, a reserved namespace, or an admission artifact field) is
duplicated.

## Digest rules

Structured fingerprints use canonical JSON: object keys sorted, no
insignificant whitespace, UTF-8, and no non-finite numbers. Tuples are encoded
as arrays. The plan digest and the strategy fingerprint exclude volatile
timestamps.

External artifacts are hashed as the exact stored bytes. A parsed document is
not written back out and then hashed in place of those bytes.
LF versus CRLF, UTF-8 versus UTF-16, a BOM, or whitespace changes therefore
invalidate the recorded artifact digest. Publishers must preserve artifact
bytes or publish a newly bound artifact chain; consumers never normalize
them into agreement. Offline program files are written as exact UTF-8 bytes
so platform newline conversion cannot invalidate the export manifest.

`strategy_fingerprint` on `ToolpathStrategy` includes ordered
`depth_levels_mm`. The traceable strategy fingerprint adds clearance and stock
allowance. A stored feed recommendation is attached to a toolpath only when
its id is selected explicitly.
Depth order is meaningful and is never sorted for a fingerprint. Requests
require strictly increasing positive depths. Earlier fingerprints that
omitted depths are intentionally not preserved: persisted plans must be
recomputed and reviewed. Request fingerprints also bind frame name and
strategy identity.

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
  axis-aligned removal rectangle over the whole of every plunge and cut,
  including the part above the stock top and below clearance
* removal rectangle inside the stock footprint; frame
  `stock-fixed-coupon-xy` puts the origin at the stock corner
* plunge and cut depth within the declared maximum and the explicit levels
* travel stays at or above the declared clearance; a retract must finish
  there and must not dive back into the stock
* profile, units, tool kind, and orientation

Motion must be continuous, finite, start and finish at clearance, and use
vertical downward plunges and vertical retracts. Cuts remain at constant Z.
The checker verifies both original and three-decimal posted coordinates;
rounding cannot extend removal bounds or lower clearance. Discrete-depth
identity uses an absolute tolerance of `1e-9` mm and zero relative tolerance.
This is numerical matching, not an allowance to exceed maximum removal;
the maximum depth comparison remains exact. This matching tolerance is part
of the local policy digest. Feeds that become zero at posting precision are
refused.

Not implemented: clamp collision beyond that rectangle, full machine
collision, structural safety, cutting force, and machine readiness. Unknown
positional tolerance is refused rather than treated as zero.

The contour planner is not implemented. The witness records
`UNSUPPORTED_CAPABILITY` and does not emit a candidate program. Explicit
linear motion used by tests is labeled `explicit_linear_motion`. It is not
planner output. Any program the offline gate renders is passed through
`cam_creation_studio.gcode.generator` and marked
`EXPERIMENTAL — NOT FOR MACHINING`.

The offline writer verifies the program/manifest digests and experimental
labels before writing. Refusals remove stale program/manifest outputs and
write a labeled `result.json`. It cannot prevent a person from modifying a
text file after export; a changed program no longer matches its manifest.

## Operator limits

There is still no real contour planner, operational publisher trust anchor,
human-review authority, or operational governed export. No label, admission
flag, fixture review, or CLI option enables these missing capabilities.
Ordinary manual generation remains available under its existing preflight
policy; it is not a governed physical-engineering approval path.

Classification detects declared provenance and attempts to relabel it. It
does not reconstruct metadata that an external actor entirely deletes, and
these library helpers are not an isolation boundary against arbitrary Python
code running in the same process. Imported artifacts must retain their
provenance when passed by clients.

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
