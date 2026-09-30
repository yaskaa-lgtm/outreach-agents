from __future__ import annotations

import asyncio
import logging

import pytest

from app.worker import __main__ as worker


async def test_worker_starts_and_stops_cleanly(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def _ping(*_args: object, **_kwargs: object) -> bool:
        return True

    monkeypatch.setattr(worker, "ping_database", _ping)
    stop = asyncio.Event()
    stop.set()  # ask the worker to stop right after start-up

    with caplog.at_level(logging.INFO, logger="app.worker"):
        await asyncio.wait_for(worker.run_worker(stop), timeout=5)

    messages = [record.getMessage() for record in caplog.records]
    assert any("Worker started" in message for message in messages)
    assert any("Worker stopped" in message for message in messages)
