"""Pytest fixtures and configuration for backend tests.

Guards against unmocked real HTTP network calls and sets retry delays to zero.
"""

import socket

import pytest

from services import open_meteo, osrm


@pytest.fixture(autouse=True)
def zero_retry_delays(monkeypatch):
    """Disable retry delays in test runs so upstream failure tests execute instantly."""
    monkeypatch.setattr(osrm, "RETRY_DELAY_S", 0.0)
    monkeypatch.setattr(open_meteo, "RETRY_DELAY_S", 0.0)


@pytest.fixture(autouse=True)
def guard_no_real_sockets(monkeypatch):
    """Guard so any real HTTP socket connect in tests fails loudly."""

    def guarded_connect(self, address):
        raise RuntimeError(
            f"Blocked real network socket connect to {address} during test execution! "
            "All external HTTP requests must be mocked."
        )

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


@pytest.fixture(autouse=True)
def clear_django_cache():
    """Ensure a clean cache state before and after each test."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
