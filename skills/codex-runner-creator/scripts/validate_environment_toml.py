#!/usr/bin/env python3
"""Validate a Codex .codex/environments/environment.toml file."""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path


def fail(message: str) -> None:
    print(f"[ERROR] {message}", file=sys.stderr)
    raise SystemExit(1)


def validate(path: Path) -> None:
    if not path.exists():
        fail(f"file does not exist: {path}")
    if not path.is_file():
        fail(f"not a file: {path}")

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        fail(f"TOML parse failed: {exc}")

    if data.get("version") != 1:
        fail("expected top-level version = 1")

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        fail("expected non-empty top-level name string")

    setup = data.get("setup")
    if not isinstance(setup, dict):
        fail("expected [setup] table")

    script = setup.get("script")
    if not isinstance(script, str):
        fail("expected [setup].script string")

    actions = data.get("actions")
    if not isinstance(actions, list) or not actions:
        fail("expected at least one [[actions]] entry")

    for index, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            fail(f"action {index} is not a table")
        for key in ("name", "icon", "command"):
            value = action.get(key)
            if not isinstance(value, str) or not value.strip():
                fail(f"action {index} missing non-empty {key} string")
        command = action["command"]
        if "\x00" in command:
            fail(f"action {index} command contains a NUL byte")
        if command.strip().startswith("sudo "):
            fail(f"action {index} command starts with sudo; require explicit review")

    print(f"[OK] {path} is a valid Codex environment file")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to environment.toml")
    args = parser.parse_args()
    validate(args.path)


if __name__ == "__main__":
    main()
