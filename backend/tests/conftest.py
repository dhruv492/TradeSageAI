"""
Module      : conftest.py
Date        : 2026-09-03
Author      : Dhruv
Synopsis:
    Repo reorg (lean-build session) moved the smoke_test_*.py files from
    the backend root into backend/tests/. They all do bare imports like
    `import app` and `import price_service`, which only works if the
    backend/ directory is on sys.path. Pytest does not add a test file's
    grandparent directory automatically, so this conftest does it
    explicitly - keeps every existing test file unchanged.
"""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
