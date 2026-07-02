"""Setup smoke test: the package imports and exposes a non-empty version.

Keeps `pytest` green from day one so every later slice has a baseline to build on.
"""

from __future__ import annotations

import churnpilot


def test_version_present():
    assert isinstance(churnpilot.__version__, str)
    assert churnpilot.__version__
