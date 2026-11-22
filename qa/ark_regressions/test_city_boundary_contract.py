"""Ark task 37698 / frore 90664: city isolation contract.

Standalone regression contract. This deliberately does not monkeypatch a
specific implementation; production adapters must be wired in before claiming
that RedTrip passes it.
"""
from __future__ import annotations

import pytest


@pytest.mark.parametrize("requested_city,forbidden_city", [
    ("北京", "上海"),
    ("上海", "北京"),
])
def test_city_boundaries_are_not_interchangeable(requested_city, forbidden_city):
    """An explicit city constraint must never be replaced by a default city."""
    assert requested_city != forbidden_city


@pytest.mark.xfail(strict=True, reason="Awaiting production city-scoped adapter")
def test_real_city_scoped_evidence_adapter():
    """Replace with actual evidence request and assert all results match city."""
    raise AssertionError("Production adapter not wired; no E2E claim")
