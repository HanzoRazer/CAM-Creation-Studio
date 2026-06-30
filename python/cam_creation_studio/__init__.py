"""CAM-Creation-Studio — Python core.

A standalone, educational learning-and-authoring core for simple CNC, laser,
and Marlin-style G-code. This package is the primary source of truth for the
project's logic: G-code generation, parsing, validation, feeds/speeds,
machine/material/tool profiles, a neutral preview model, image-etch toolpaths,
and safety warnings.

IMPORTANT: This is an EDUCATIONAL tool. Nothing here is a certified
post-processor, and no output is guaranteed safe to run. Always verify a program
before running it on real hardware.

The browser/JS prototype under ``app/`` and ``src/`` is preserved as a
behavioral reference and provenance archive; this Python package is the real
application core.
"""

__version__ = "0.1.0"

APP_NAME = "CAM-Creation-Studio"
