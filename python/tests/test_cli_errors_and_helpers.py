"""CLI error mapping and formatting helpers (CS-007)."""

import json


from cam_creation_studio.cli import errors, output
from cam_creation_studio.cli.main import main


# --- exit-code mapping ------------------------------------------------------

def test_exit_code_for_cli_errors():
    assert errors.exit_code_for(errors.UsageError("x")) == errors.EXIT_USAGE
    assert errors.exit_code_for(errors.FileError("x")) == errors.EXIT_FILE
    assert errors.exit_code_for(errors.ValidationFailure("x")) == errors.EXIT_VALIDATION


def test_exit_code_for_builtin_exceptions():
    assert errors.exit_code_for(FileNotFoundError()) == errors.EXIT_FILE
    assert errors.exit_code_for(PermissionError()) == errors.EXIT_FILE
    assert errors.exit_code_for(json.JSONDecodeError("m", "d", 0)) == errors.EXIT_USAGE
    assert errors.exit_code_for(ValueError()) == errors.EXIT_USAGE
    assert errors.exit_code_for(RuntimeError()) == errors.EXIT_VALIDATION


def test_generate_write_to_bad_path_is_file_error(tmp_path, capsys):
    job = tmp_path / "job.json"
    job.write_text(json.dumps({"config": {"machine": "genericCnc", "units": "mm"},
                               "job": {"mode": "manual", "moves": []}}),
                   encoding="utf-8")
    # Generation succeeds; a directory as the output path cannot be written as a file.
    assert main(["generate", str(job), "-o", str(tmp_path)]) == 3
    assert "cannot write" in capsys.readouterr().err


# --- output helpers ---------------------------------------------------------

def test_format_table_aligns_and_has_separator():
    table = output.format_table(["a", "bb"], [[1, 2], [333, 4]])
    lines = table.splitlines()
    assert lines[0].startswith("a")
    assert set(lines[1]) <= {"-", " "}
    assert "333" in lines[3]


def test_kv_block_renders_none_as_dash():
    block = output.kv_block([("x", 1), ("y", None)], title="T")
    assert block.startswith("T")
    assert "-" in block.splitlines()[-1]


def test_render_json_vs_human(capsys):
    printed = output.render(json_mode=True, human_text="H", json_obj={"k": 1})
    assert json.loads(printed) == {"k": 1}
    printed = output.render(json_mode=False, human_text="H", json_obj={"k": 1})
    assert printed == "H"


# --- package surface --------------------------------------------------------

def test_generate_core_failure_is_usage_error(tmp_path, capsys):
    # A valid document whose config drives the generator into an error
    # (unknown dialect) surfaces as a usage error, not a crash.
    job = tmp_path / "job.json"
    job.write_text(json.dumps({"config": {"machine": "nope"},
                               "job": {"mode": "manual", "moves": []}}),
                   encoding="utf-8")
    assert main(["generate", str(job)]) == 2
    assert "could not generate" in capsys.readouterr().err
