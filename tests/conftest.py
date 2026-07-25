"""Shared fixtures.

The app builds its stores at import time from ARGYBARGY_DATA, so we point that
at a throwaway directory *before* anything imports `argybargy.app`. pytest loads
conftest first, which makes a bare `pytest` safe — it can never touch a real
~/.argybargy.
"""
import os
import socket
import tempfile
import threading
import time

import pytest

os.environ.setdefault("ARGYBARGY_DATA", tempfile.mkdtemp(prefix="argybargy-test-"))

from fastapi.testclient import TestClient  # noqa: E402

from argybargy import app as appmod  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(appmod.app)


@pytest.fixture(scope="session")
def admin_headers() -> dict:
    return {"X-Admin-Token": appmod.ADMIN_TOKEN}


@pytest.fixture
def make_code():
    """Mint a real access code. Returns (code, auth_headers)."""
    minted = []

    def _make(name: str, room: str = "default", **kw):
        code = appmod.code_store.issue(name=name, room=room, **kw)
        minted.append(name)
        return code, {"Authorization": f"Bearer {code}"}

    yield _make
    for name in minted:
        appmod.code_store.revoke(name)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server():
    """Serve the real ASGI app over HTTP so a browser can drive it.

    Same app instance the API tests use, so codes minted either way are visible
    to both.
    """
    import uvicorn

    port = _free_port()
    config = uvicorn.Config(appmod.app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 30
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("live server did not start")

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=10)
