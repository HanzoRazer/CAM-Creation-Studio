"""SCAFFOLD-DIST-001 — integration self-test for scaffold_agents_md.py.

Ported for CAM-Creation-Studio.

The original test assumed it lived in ``scripts/ci`` beside a repository-owned
``scripts/scaffold_agents_md.py``. CAM-Creation-Studio has a different layout:
its Python tests live under ``python/tests`` and the repository currently uses a
top-level ``tools`` directory rather than a top-level ``scripts`` directory.

This version therefore discovers the repository root instead of relying on a
fixed number of ``parents[]`` hops, and resolves the scaffolder from:

1. ``CAMSTUDIO_SCAFFOLDER`` — explicit path override, useful when the
   distribution tool is supplied from a sibling/portfolio tools checkout;
2. ``<repo>/tools/scaffold_agents_md.py`` — preferred CAM-Creation-Studio
   location if the tool is vendored here later;
3. ``<repo>/scripts/scaffold_agents_md.py`` — compatibility with the original
   distribution layout.

If none exists, these integration tests are skipped with a precise reason. That
keeps CAM-Creation-Studio's normal test suite valid without pretending that a
tool this repository does not currently contain has been exercised.

The behavioral contract remains intentionally environment-driven: every test
creates a real temporary git repository and invokes the real CLI as a
subprocess. No git/environment behavior is mocked.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _find_repo_root(start: Path) -> Path:
    """Return the nearest CAM-Creation-Studio/repository root.

    We key on ``.git`` when available, with ``python`` + ``README.md`` as a
    fallback for source archives and exported worktrees where ``.git`` may not
    be a normal directory.
    """
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
        if (candidate / "README.md").is_file() and (candidate / "python").is_dir():
            return candidate
    raise RuntimeError(f"could not locate repository root from {start}")


REPO_ROOT = _find_repo_root(Path(__file__).parent)


def _resolve_scaffolder() -> Path | None:
    """Resolve the real scaffold CLI without assuming another repo's layout."""
    override = os.environ.get("CAMSTUDIO_SCAFFOLDER")
    candidates: list[Path] = []

    if override:
        p = Path(override).expanduser()
        if not p.is_absolute():
            p = REPO_ROOT / p
        candidates.append(p)

    candidates.extend(
        [
            REPO_ROOT / "tools" / "scaffold_agents_md.py",
            REPO_ROOT / "scripts" / "scaffold_agents_md.py",
        ]
    )

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


@pytest.fixture(scope="session")
def scaffolder() -> Path:
    """Real CLI under test.

    CAM-Creation-Studio does not currently own this utility. Skipping when it is
    absent is deliberate; set CAMSTUDIO_SCAFFOLDER to exercise an external
    distribution checkout in CI or locally.
    """
    path = _resolve_scaffolder()
    if path is None:
        pytest.skip(
            "scaffold_agents_md.py is not present in CAM-Creation-Studio; "
            "set CAMSTUDIO_SCAFFOLDER or add tools/scaffold_agents_md.py"
        )
    return path


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _make_repo(
    root: Path,
    *,
    name: str = "repo",
    remote: str | None = None,
    branch: str = "main",
    origin_head: bool = True,
) -> Path:
    """Create a real git repo with one commit and optionally a fake origin."""
    repo = root / name
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", branch)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "init")

    if remote:
        _git(repo, "remote", "add", "origin", remote)
        if origin_head:
            # Simulate a resolvable origin/HEAD without a network remote.
            _git(repo, "update-ref", f"refs/remotes/origin/{branch}", "HEAD")
            _git(
                repo,
                "symbolic-ref",
                "refs/remotes/origin/HEAD",
                f"refs/remotes/origin/{branch}",
            )
    return repo


def _run_scaffolder(
    scaffolder: Path,
    repo: Path,
    *extra: str,
) -> subprocess.CompletedProcess[str]:
    """Invoke the real CLI with stdin closed -- the agent-session condition."""
    return subprocess.run(
        [sys.executable, str(scaffolder), str(repo), *extra],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        timeout=60,
        check=False,
    )


# --------------------------------------------------------------------------- #
# 1. Worktree repo-name
# --------------------------------------------------------------------------- #

def test_heading_uses_remote_name_not_directory_name(
    tmp_path: Path, scaffolder: Path
) -> None:
    """A worktree directory name must not become the repository identity."""
    repo = _make_repo(
        tmp_path,
        name="cam-task-worktree",
        remote="https://example.com/org/CAM-Creation-Studio.git",
    )
    assert _run_scaffolder(scaffolder, repo).returncode == 0

    heading = (repo / "AGENTS.md").read_text(encoding="utf-8").splitlines()[0]
    assert heading == "# Agent instructions — CAM-Creation-Studio"
    assert "cam-task-worktree" not in heading


# --------------------------------------------------------------------------- #
# 2. Case-folded PR-template discovery
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("where", [".github", "", "docs"])
@pytest.mark.parametrize(
    "casing",
    ["PULL_REQUEST_TEMPLATE.md", "pull_request_template.md"],
)
def test_existing_template_is_found_in_any_casing_or_location(
    tmp_path: Path,
    scaffolder: Path,
    where: str,
    casing: str,
) -> None:
    repo = _make_repo(
        tmp_path,
        name=f"r{len(where)}{len(casing)}",
        remote="https://example.com/o/r.git",
    )
    target_dir = repo / where if where else repo
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / casing).write_text("existing\n", encoding="utf-8")

    result = _run_scaffolder(scaffolder, repo)
    assert result.returncode == 0
    assert "already exists" in result.stdout
    assert (target_dir / casing).read_text(encoding="utf-8") == "existing\n"

    found = [
        p
        for d in (repo, repo / ".github", repo / "docs")
        if d.is_dir()
        for p in d.iterdir()
        if p.is_file() and p.name.casefold() == "pull_request_template.md"
    ]
    assert len(found) == 1, f"a second template was written: {found}"


# --------------------------------------------------------------------------- #
# 3. Non-TTY --force
# --------------------------------------------------------------------------- #

def test_force_without_yes_refuses_headlessly_and_writes_nothing(
    tmp_path: Path, scaffolder: Path
) -> None:
    repo = _make_repo(
        tmp_path,
        name="r3a",
        remote="https://example.com/o/r3a.git",
    )
    (repo / "AGENTS.md").write_text("ORIGINAL\n", encoding="utf-8")

    result = _run_scaffolder(scaffolder, repo, "--force")
    assert result.returncode != 0
    assert "EOFError" not in result.stderr
    assert "Traceback" not in result.stderr
    assert (repo / "AGENTS.md").read_text(encoding="utf-8") == "ORIGINAL\n"


def test_force_with_yes_overwrites_headlessly(
    tmp_path: Path, scaffolder: Path
) -> None:
    repo = _make_repo(
        tmp_path,
        name="r3b",
        remote="https://example.com/o/r3b.git",
    )
    (repo / "AGENTS.md").write_text("ORIGINAL\n", encoding="utf-8")

    result = _run_scaffolder(scaffolder, repo, "--force", "--yes")
    assert result.returncode == 0

    body = (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert "ORIGINAL" not in body
    assert body.startswith("# Agent instructions — r3b")


# --------------------------------------------------------------------------- #
# 4. Undetectable default branch must never be written silently
# --------------------------------------------------------------------------- #

def test_undetectable_default_branch_refuses_headlessly(
    tmp_path: Path, scaffolder: Path
) -> None:
    repo = _make_repo(tmp_path, name="r4", branch="develop", remote=None)

    result = _run_scaffolder(scaffolder, repo)
    assert result.returncode != 0, "wrote on a guessed default branch"
    assert not (repo / "AGENTS.md").exists()
    assert "could not detect the default branch" in result.stderr
    assert "--default-branch" in result.stderr


def test_default_branch_override_is_used_throughout(
    tmp_path: Path, scaffolder: Path
) -> None:
    repo = _make_repo(tmp_path, name="r4b", branch="develop", remote=None)

    result = _run_scaffolder(
        scaffolder,
        repo,
        "--default-branch",
        "develop",
    )
    assert result.returncode == 0

    body = (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert "## Branch from current `develop`. Always." in body
    assert "origin/develop" in body
    assert "git merge-base HEAD origin/develop" in body
    assert "origin/main" not in body


# --------------------------------------------------------------------------- #
# 5. Happy path and never-overwrite default
# --------------------------------------------------------------------------- #

def test_happy_path_writes_both_with_todo_blocks_unfilled(
    tmp_path: Path, scaffolder: Path
) -> None:
    repo = _make_repo(
        tmp_path,
        name="r5",
        remote="https://example.com/o/r5.git",
    )

    result = _run_scaffolder(scaffolder, repo)
    assert result.returncode == 0

    agents = (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert (repo / ".github" / "pull_request_template.md").exists()

    assert "<!-- INCIDENTS" in agents
    assert "<!-- VERIFICATION GATES" in agents
    assert "NOT DONE" in result.stdout


def test_second_run_does_not_clobber(
    tmp_path: Path, scaffolder: Path
) -> None:
    repo = _make_repo(
        tmp_path,
        name="r5b",
        remote="https://example.com/o/r5b.git",
    )
    assert _run_scaffolder(scaffolder, repo).returncode == 0

    (repo / "AGENTS.md").write_text("HAND EDITED\n", encoding="utf-8")

    result = _run_scaffolder(scaffolder, repo)
    assert result.returncode == 0
    assert (repo / "AGENTS.md").read_text(encoding="utf-8") == "HAND EDITED\n"
    assert "SKIP" in result.stdout


def test_refuses_a_non_git_directory(
    tmp_path: Path, scaffolder: Path
) -> None:
    plain = tmp_path / "not-a-repo"
    plain.mkdir()

    result = _run_scaffolder(scaffolder, plain)
    assert result.returncode == 2
    assert not (plain / "AGENTS.md").exists()
