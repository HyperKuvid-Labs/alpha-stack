# conftest to ensure the project root is on sys.path during tests
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# Normalize sys.path entries to absolute paths
paths = [os.path.abspath(p) for p in sys.path]
if ROOT not in paths:
    sys.path.insert(0, ROOT)
