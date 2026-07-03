# CAM Creation Studio

> **A Python-first manufacturing execution laboratory for learning, authoring, validating, and understanding G-code.**

CAM Creation Studio is a standalone application focused on **manufacturing execution**, not manufacturing governance.

It began as a G-code tutorial and has evolved into a broader environment for developing machining knowledge through G-code authoring, feeds & speeds calculation, toolpath analysis, validation, and operator education.

Unlike traditional CAM systems, CAM Creation Studio is **not intended to replace commercial CAM software**. Its purpose is to help users understand and refine machining operations while remaining independent of any specific CAD system, CAM package, or CNC controller.

---

# Project Goals

CAM Creation Studio provides a practical environment for:

* Manual G-code authoring
* G-code learning and education
* G-code parsing and validation
* Feeds & speeds calculations
* Tool and material libraries
* Machine profiles
* Toolpath visualization
* Manufacturing diagnostics
* Operator training
* Manufacturing experimentation

The project emphasizes **understanding manufacturing execution**, rather than automating it.

---

# Constitutional Purpose

CAM Creation Studio answers questions such as:

* What feed rate should I start with?
* What spindle speed is appropriate?
* What does this G-code actually do?
* Is this program internally consistent?
* What warnings should I review before machining?
* How will this toolpath move?
* How can I improve this operation?

It is designed to make machining knowledge understandable, reviewable, and reusable.

---

# What This Project Is

CAM Creation Studio is:

* A Python application
* A manufacturing execution workspace
* A G-code learning environment
* A feeds & speeds calculator
* A G-code validator
* A toolpath analysis framework
* A machining education platform
* A foundation for future CNC utilities

---

# What This Project Is Not

CAM Creation Studio is **not**:

* A commercial CAM replacement
* A certified post-processor
* A CNC machine controller
* A machine sender
* A production simulator
* A machine safety certification system

Generated information should always be reviewed by a qualified operator before machining.

---

# Relationship to CAM Assist Blueprint

Although the repositories are related, they serve different constitutional responsibilities.

## CAM Assist Blueprint

Owns:

* Manufacturing intent
* Design assumptions
* Review
* Risk
* Approval
* Traceability
* Manufacturing strategy
* Human authority

Produces:

> Manufacturing Knowledge

---

## CAM Creation Studio

Owns:

* G-code
* Feeds & speeds
* Toolpath analysis
* Machine profiles
* Material profiles
* Validation
* Operator education
* Manufacturing execution support

Produces:

> Manufacturing Execution Information

---

The repositories intentionally remain separate.

CAM Assist explains **why** a machining strategy exists.

CAM Creation Studio helps determine **how** that strategy is executed.

---

# Design Philosophy

The project follows several core principles:

## Python First

Python is the primary implementation language.

Archived HTML prototypes serve as behavioral references only.

Future interfaces (desktop or web) will use the Python core rather than duplicate business logic.

---

## Machine Independence

The application avoids dependence on any specific controller whenever practical.

Machine-specific behavior is represented through configurable profiles rather than hard-coded implementations.

---

## Educational First

Every feature should help users better understand machining.

The software should explain—not simply generate.

---

## Advisory Authority

Feeds, speeds, diagnostics, and recommendations are advisory.

The operator remains responsible for:

* Machine setup
* Workholding
* Tool selection
* Safe operation
* Final verification

---

# Planned Architecture

```text
CAM Creation Studio

├── G-code Generation
├── G-code Parser
├── G-code Validator
├── Feeds & Speeds
├── Tool Library
├── Material Library
├── Machine Profiles
├── Toolpath Model
├── Image Processing
├── Preview Engine
└── Future UI
```

The Python core remains independent of any user interface.

---

# Repository Structure

The Python core lives under `python/cam_creation_studio/`:

```text
cam_creation_studio/
│
├── gcode/
│   ├── generator.py
│   ├── parser.py
│   ├── validator.py
│   ├── formatter.py
│   └── dialects.py
│
├── feeds_speeds/
│   ├── calculator.py
│   ├── materials.py
│   ├── machines.py
│   └── tools.py
│
├── preview/
│   └── toolpath_model.py
│
├── image/
│   ├── field.py
│   ├── marching_squares.py
│   ├── raster_etch.py
│   └── outline_etch.py
│
├── safety/
│   └── rules.py
│
├── handoff/
│   └── handoff.py
│
└── shared/
    ├── numbers.py
    └── units.py
```

The archived HTML prototypes and the browser reference app live under
`archive/original-html/`, `app/`, and `src/`. See `docs/architecture.md`.

---

# Getting Started

The core is a headless Python package with no third-party runtime dependencies.

```bash
cd python
python -m pytest        # run the full test suite
pip install -e .[dev]   # optional: editable install with dev tools
```

Example:

```python
from cam_creation_studio.gcode.generator import build_program
from cam_creation_studio.gcode.validator import validate_program
from cam_creation_studio.feeds_speeds.calculator import calculate_feeds

cfg = {"machine": "genericCnc", "units": "mm", "positioning": "abs",
       "home": True, "spindleOn": True, "spindleRpm": 12000, "safeZ": 5}
job = {"mode": "manual", "moves": [
    {"type": "G0", "x": "0", "y": "0"},
    {"type": "G1", "z": "-0.5", "f": "300"},
    {"type": "G1", "x": "40", "f": "800"},
]}

program = build_program(cfg, job)
warnings = validate_program(program, machine="genericCnc")   # advisory only
feeds = calculate_feeds(tool_diameter_mm=6.0, flutes=2, spindle_rpm=12000, material="mdf")
```

---

# Future Roadmap

Planned development includes:

* G-code editing tools
* Interactive toolpath visualization
* DXF import
* Image-to-toolpath utilities
* Drag knife support
* Laser engraving support
* Tool libraries
* Material databases
* Machine profile expansion
* Machining calculators
* Cutting parameter optimization
* Manufacturing diagnostics
* Educational tutorials

---

# Safety Notice

CAM Creation Studio produces **educational and advisory manufacturing information**.

It does **not** guarantee:

* machine safety
* machining success
* collision avoidance
* proper workholding
* suitable tooling
* correct cutting parameters

Always verify generated programs through simulation, dry runs, and established shop safety procedures before machining.

---

# License

This project is released under the MIT License.

See `LICENSE` for details.

---

# Vision

The long-term vision is to establish **CAM Creation Studio** as an open, modular environment where machinists, makers, educators, and CNC programmers can learn, experiment, validate, and refine manufacturing execution while remaining independent of any single CAD, CAM, or CNC ecosystem. It complements manufacturing governance tools such as CAM Assist Blueprint while maintaining a clear focus on the practical aspects of machining execution and operator education.
