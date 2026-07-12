"""Command-line interface for CAM-Creation-Studio (CS-007).

A thin presentation layer over the Python core. It owns argument parsing,
output formatting, and exit codes — never business logic, calculations, or
validation rules. Every command follows the same shape: read input, call the
library, display the result.

The console entry point is ``camstudio`` (``cam_creation_studio.cli.main:main``
in ``pyproject.toml``); the same dispatch is reachable as
``python -m cam_creation_studio.cli``.
"""
