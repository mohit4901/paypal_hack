"""Structured logging configuration — never logs secrets or PII."""
from __future__ import annotations
import logging
import re
import sys

# Patterns to redact from log output
_REDACT_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]+"),
    re.compile(r"client_secret=[^&\s]+"),
    re.compile(r"access_token[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9\-_\.]+"),
    re.compile(r"password[\"']?\s*[:=]\s*[\"']?[^\s\"']+"),
]


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        for pat in _REDACT_PATTERNS:
            msg = pat.sub("[REDACTED]", msg)
        return msg


def setup_logging(level: str = "INFO", name: str = "proofledger") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        RedactingFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    return logger

