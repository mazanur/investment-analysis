"""Tests for Alembic migrations against a real PostgreSQL database.

Requires a running PostgreSQL instance (docker compose up -d db).
These tests verify that upgrade/downgrade cycles work correctly.
"""

import socket
import subprocess
import sys
from pathlib import Path

import pytest

ALEMBIC_CMD = [sys.executable, "-m", "alembic"]
PROJECT_DIR = str(Path(__file__).resolve().parent.parent)


def _pg_is_available(host: str = "localhost", port: int = 5434) -> bool:
    """Check if PostgreSQL is reachable."""
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _pg_is_available(), reason="PostgreSQL not running on localhost:5434"
)


def run_alembic(*args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [*ALEMBIC_CMD, *args],
        capture_output=True,
        text=True,
        cwd=PROJECT_DIR,
    )
    return result


@pytest.fixture(autouse=True)
def _ensure_clean_db():
    """Downgrade to base before and after each test."""
    run_alembic("downgrade", "base")
    yield
    run_alembic("downgrade", "base")


def test_upgrade_head():
    """Test that upgrade to head succeeds."""
    result = run_alembic("upgrade", "head")
    assert result.returncode == 0, f"upgrade failed: {result.stderr}"
    assert "Running upgrade" in result.stderr


def test_downgrade_base():
    """Test that downgrade to base succeeds after upgrade."""
    upgrade = run_alembic("upgrade", "head")
    assert upgrade.returncode == 0, f"upgrade failed: {upgrade.stderr}"

    downgrade = run_alembic("downgrade", "base")
    assert downgrade.returncode == 0, f"downgrade failed: {downgrade.stderr}"
    assert "Running downgrade" in downgrade.stderr


def test_upgrade_downgrade_upgrade_cycle():
    """Test full upgrade -> downgrade -> upgrade cycle is idempotent."""
    r1 = run_alembic("upgrade", "head")
    assert r1.returncode == 0, f"first upgrade failed: {r1.stderr}"

    r2 = run_alembic("downgrade", "base")
    assert r2.returncode == 0, f"downgrade failed: {r2.stderr}"

    r3 = run_alembic("upgrade", "head")
    assert r3.returncode == 0, f"second upgrade failed: {r3.stderr}"


def test_current_shows_head_after_upgrade():
    """Test that 'alembic current' shows head revision after upgrade."""
    run_alembic("upgrade", "head")
    result = run_alembic("current")
    assert result.returncode == 0
    assert "(head)" in result.stdout


def test_no_pending_migrations():
    """Test that autogenerate finds no differences after upgrade."""
    run_alembic("upgrade", "head")
    result = run_alembic("check")
    assert result.returncode == 0, (
        f"There are pending model changes not in migrations: {result.stderr}"
    )
