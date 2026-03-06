#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ALLOWED_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".html"}
EXCLUDED_PARTS = {
    ".git",
    ".cursor",
    ".playwright-cli",
    ".aws-sam",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "vendor",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "htmlcov",
    "assets",
    "icons",
    "images",
    "img",
    "fonts",
    "media",
}


def run_git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def is_git_repo(cwd: Path) -> bool:
    try:
        run_git(cwd, "rev-parse", "--show-toplevel")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def git_root(cwd: Path) -> Path:
    return Path(run_git(cwd, "rev-parse", "--show-toplevel").strip())


def normalize_path(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def is_allowed_file(path: Path) -> bool:
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        return False

    lowered_parts = {part.lower() for part in path.parts}
    return lowered_parts.isdisjoint(EXCLUDED_PARTS)


def iter_allowed_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    if path.is_file():
        return [path] if is_allowed_file(path) else []

    matches: list[Path] = []
    for candidate in path.rglob("*"):
        if candidate.is_file() and is_allowed_file(candidate):
            matches.append(candidate)
    return matches


def changed_files(root: Path) -> list[Path]:
    output = run_git(root, "status", "--short", "--untracked-files=all")
    candidates: set[Path] = set()

    for raw_line in output.splitlines():
        if len(raw_line) < 4:
            continue
        path_text = raw_line[3:]
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        candidate = (root / path_text).resolve()
        if candidate.exists() and candidate.is_file() and is_allowed_file(candidate.relative_to(root)):
            candidates.add(candidate)

    return sorted(candidates)


def collect_from_args(cwd: Path, raw_paths: list[str]) -> list[str]:
    collected: set[str] = set()

    for raw_path in raw_paths:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = (cwd / candidate).resolve()
        for match in iter_allowed_files(candidate):
            collected.add(normalize_path(match, cwd))

    return sorted(collected)


def collect_from_cwd(cwd: Path) -> list[str]:
    collected: set[str] = set()
    for match in iter_allowed_files(cwd):
        collected.add(normalize_path(match, cwd))
    return sorted(collected)


def main() -> int:
    cwd = Path.cwd()
    raw_paths = sys.argv[1:]

    if raw_paths:
        results = collect_from_args(cwd, raw_paths)
    elif is_git_repo(cwd):
        root = git_root(cwd)
        workspace = cwd.resolve()
        results = []
        for path in changed_files(root):
            try:
                path.resolve().relative_to(workspace)
            except ValueError:
                continue
            results.append(normalize_path(path, workspace))
    else:
        results = collect_from_cwd(cwd)

    for result in results:
        print(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
