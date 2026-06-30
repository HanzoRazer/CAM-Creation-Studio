# Product Scope

This is the constitutional scope document for CAM-Creation-Studio. When in
doubt about whether something belongs in this project, this document decides.

## Purpose

CAM-Creation-Studio is a **standalone, beginner-to-shop utility for learning,
creating, previewing, validating, and refining simple G-code**, with
feeds-and-speeds support. It began as a G-code tutorial and is being formalized
into a structured, browser-first authoring environment.

It is an **execution-adjacent learning and authoring environment** — it helps
people get close to running a machine (understanding code, previewing motion,
estimating feeds) without claiming any machine authority itself.

## Users

- Beginners learning to read and write G-code.
- Hobbyists and small shops authoring simple programs by hand or from an image.
- Educators demonstrating G/M-codes, program structure, and dialect differences.

## In scope

- G-code education.
- Manual G-code authoring.
- Image-to-etch workflows (raster fill, vector outline).
- Feeds and speeds (advisory only).
- Tool / material / machine presets (conservative, editable).
- Preview and (non-blocking) validation.
- Execution-adjacent learning tools.

## Out of scope

- Certified post-processors and "production-ready" machine output.
- Machine execution, sender/streaming to a controller.
- Real collision or material-removal simulation.
- Automatic machining approval or closed-loop optimization.
- Cloud accounts and database persistence.
- Any CAM Assist dependency, parser, or schema enforcement.

> **CAM-Creation-Studio does not certify machine readiness, replace professional
> CAM validation, or guarantee safe machine execution.**

## Safety position

- Generated G-code is a **starting point**, not certified output.
- Preview is **not** simulation.
- Feeds/speeds are a **suggested starting point that requires operator verification**.
- The app uses language like *machine output profiles*, *starter dialect
  profiles*, and *educational G-code templates* — never *production-ready post
  processor*, *machine-certified output*, or *safe to run*.

See [safety-disclaimer.md](safety-disclaimer.md).

## Relationship to CAM Assist

CAM-Creation-Studio is its **own repository** and stays standalone. CAM Assist
does **not** own G-code, feeds/speeds, simulation, machine readiness,
post-processing, or execution claims here. No dependency is introduced in this
phase. See [future-cam-assist-relationship.md](future-cam-assist-relationship.md).

## Future expansion

- A non-blocking validator with safety warnings.
- A fuller feeds/speeds calculator with presets.
- Extracted, independently tested preview and image modules.

**Architecture direction (updated):** the project core is now built as a
**Python package** ([`../python`](../python)) — it is the primary source of
truth for generation, parsing, validation, feeds/speeds, presets, the preview
model, image-etch logic, and safety warnings. The browser app is retained as a
prototype and behavioral reference. A future UI is an optional wrapper around
the Python core. See [architecture.md](architecture.md).
