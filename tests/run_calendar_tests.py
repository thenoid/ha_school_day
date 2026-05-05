"""Minimal test runner for environments without pytest."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def main() -> None:
    test_path = Path(__file__).with_name("test_calendar.py")
    spec = importlib.util.spec_from_file_location("test_calendar", test_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {test_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for name in sorted(dir(module)):
        if name.startswith("test_"):
            getattr(module, name)()


if __name__ == "__main__":
    main()

