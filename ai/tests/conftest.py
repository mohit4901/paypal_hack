"""
Global pytest configuration and isolation fixtures for ProofLedger test suite.
"""
from __future__ import annotations

import os
from pathlib import Path
import pytest

from src.storage.db import init_db


@pytest.fixture(autouse=True)
def isolate_test_environment(tmp_path, monkeypatch):
    """
    Autouse fixture that runs before every test:
    1. Sets DATABASE_PATH to an isolated SQLite file in tmp_path.
    2. Sets CHAIN_LOG_PATH to an isolated JSONL file in tmp_path.
    3. Sets mock PAYPAL_WEBHOOK_ID so tests don't require external secrets.
    4. Initializes isolated SQLite schema.
    
    Guarantees production data/events_hash_chain.jsonl and data/proofledger.db
    remain 100% untouched and protected from test side-effects.
    """
    test_db = str(tmp_path / "test_proofledger.db")
    test_chain = str(tmp_path / "test_events_hash_chain.jsonl")

    monkeypatch.setenv("DATABASE_PATH", test_db)
    monkeypatch.setenv("CHAIN_LOG_PATH", test_chain)
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "mock_webhook_id_test")

    init_db(test_db)

    return {
        "db_path": test_db,
        "chain_path": test_chain,
    }

