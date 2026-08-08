# Cross-Repository Boundaries

**Order:** CS-REC-05 · **Status:** permanent engineering policy
**Origin:** the 2026-08-07 contamination incident —
[`../SESSION_INTEGRITY_2026-08-07.md`](../SESSION_INTEGRITY_2026-08-07.md)

Four adjacent products share a problem domain and must not share a backlog.
This document states who owns what, and what must be true before work crosses a
boundary.

> **Enforcement:** none of this is checked by CI. These are process requirements
> upheld by people, so "must" here means "is required, and a reviewer may catch
> it" — not "the system will stop you." The import boundaries in §2 are the only
> part a linter could plausibly enforce today; that is unissued work. Judgement
> still applies: these rules exist to prevent misrouted *work*, not to block a
> five-minute read of a sibling repository for evidence, which §3 explicitly
> permits.

---

## 1. Ownership

| Product | Owns | Does **not** own |
|---------|------|------------------|
| **Luthier's Toolbox** | Instrument design; engineering calculation; the incumbent CAM implementations | Creation Studio's authoring experience |
| **CAM-Assist-Blueprint** | Manufacturing **governance** — traceability, capability profiles, review packets | G-code generation; execution |
| **CAM-Creation-Studio** | Manufacturing **execution** — G-code authoring, parsing, advisory validation, export preflight, geometry import | Instrument design; manufacturing governance; machine authority |
| **CNC-Production-Shop** | Commercial engine — cost, bid, proposal | Design; CAM; toolpaths |

Adjacency is deliberate. **Shared vocabulary is not shared authority.**

### Ratified constraints already binding here

- The Toolbox is the incumbent design **and** manufacturing runtime. Creation
  Studio does not independently reimplement its CAM algorithms — see
  [`../architecture/CAM_CREATION_STUDIO_PRODUCT_BOUNDARY.md`](../architecture/CAM_CREATION_STUDIO_PRODUCT_BOUNDARY.md)
  §7 (ratified 2026-08-05).
- `docs/product-scope.md` places any CAM Assist dependency, parser, or schema
  enforcement **out of scope** for this repository.
- Creation Studio asserts no machine readiness or certification — see
  [`../architecture/EXPORT_PREFLIGHT_SEMANTICS.md`](../architecture/EXPORT_PREFLIGHT_SEMANTICS.md).

---

## 2. Shared contracts

Nothing crosses a repository boundary except through an explicit, **versioned**
contract. Neither repository imports the other's internals: Creation Studio must
not import from `services/api/app/**`, and no sibling imports from
`python/cam_creation_studio/**`.

A shared contract requires a schema version, an owning repository, a documented
compatibility policy, and consumer tests on both sides. Absent those, the
correct answer is an adapter — not a dependency.

---

## 3. Planning authority

**Cross-repository planning is never authoritative without repository-local
confirmation.**

A recommendation derived from another repository's state is a *hypothesis*. It
becomes actionable only once confirmed against this repository: the files exist,
the tests run, the behavior reproduces. This is not ceremony — during the
incident, three claims sourced from another thread were checked here; one was
confirmed, one was disproved, and one described an artifact that had been merged
to `main` all along.

### Session rooting

**Work is performed only in a session rooted at the repository being changed.**

Cross-repository work executed from the wrong root is what produced the
incident. A session rooted in repository A may *read* repository B for evidence,
clearly labelled as such, but must not plan, refactor, or issue dev orders for
B. Rebuilding B's roadmap from an A-rooted session reproduces the failure while
appearing to fix it.

### Concurrent sessions

More than one session may operate in a repository simultaneously, and they
cannot see each other. Before opening an implementation PR, **enumerate open PRs
and remote branches.** Skipping that step produced two independent fixes for the
same defect (PRs #13 and #14), touching the same files.

---

## 4. Order intake

Every dev order carries the provenance header defined in
[`../dev_orders/LEDGER.md`](../dev_orders/LEDGER.md) and is rejected as
misrouted when the repository is not this one, the parent artifact is not
locatable here, or the identifier is retired.

Identifier namespaces never overlap and are never reused: `CS-xxx` /
`CS-REC-xx` for Creation Studio, `CAM-Axx` for Blueprint. `CAM-CS-xx` is retired
precisely because it read as belonging to both.

---

## 5. Escalation

When an order cannot be reconciled with this document, **stop and report** —
state what does not reconcile, what was verified, and what is needed. Do not
proceed on a best guess and do not silently narrow scope to whatever seems safe.

The single most reliable signal that a boundary has been crossed: an order
referring to work this repository has no record of.

Check in this order, and note that it is deliberately **not** the ledger first:

1. **`main`** — the merged tree. `git ls-tree -r origin/main`.
2. **Open PRs and remote branches** — `gh pr list`, `git branch -r`. Another
   session's work is invisible until you look.
3. **[`../dev_orders/LEDGER.md`](../dev_orders/LEDGER.md)** — for *why* something
   was decided, once you know what exists.

Report only after all three come back empty. The ledger comes last because it is
a description of the repository, not the repository; a missing ledger row means
the ledger is stale at least as often as it means the work is absent. Searching a
summary before searching the tree is precisely the mistake recorded in
[`../SESSION_INTEGRITY_2026-08-07.md`](../SESSION_INTEGRITY_2026-08-07.md) §4.1,
where an artifact was declared missing while it sat merged on `main`.
