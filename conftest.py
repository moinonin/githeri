"""Pytest configuration — make scripts/ importable as a top-level package."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "scripts"))
