"""
A minimal sitecustomize to ensure the project root is on sys.path for test environments.
This helps pytest/import imports resolve modules like 'solution' reliably regardless of working directory.
"""
import sys
import os

ROOT = os.path.abspath(os.path.dirname(__file__))
# Prepend the project root to sys.path if not already present
existing = [os.path.abspath(p) for p in sys.path]
if ROOT not in existing:
    sys.path.insert(0, ROOT)
