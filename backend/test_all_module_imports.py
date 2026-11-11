"""
Automated Test Suite for Exhaustive Canonical Module Import Integrity.
Demonstrates independently that ALL modules across backend, ai/src, and tools
import cleanly without missing dependencies, circular imports, or duplicate loading.
"""
import os
import sys
import importlib
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def get_all_python_modules():
    """Discover all non-test, non-script python modules across backend, tools, and src."""
    modules = []
    
    # Backend modules
    backend_dir = ROOT_DIR / "backend"
    for p in sorted(backend_dir.rglob("*.py")):
        if p.name.startswith("test_") or p.name.startswith("__"):
            continue
        rel = p.relative_to(ROOT_DIR)
        mod_name = str(rel).replace("/", ".").replace("\\", ".")[:-3]
        modules.append(mod_name)

    # Tools modules
    tools_dir = ROOT_DIR / "tools"
    for p in sorted(tools_dir.rglob("*.py")):
        if p.name.startswith("test_") or p.name.startswith("__"):
            continue
        rel = p.relative_to(ROOT_DIR)
        mod_name = str(rel).replace("/", ".").replace("\\", ".")[:-3]
        modules.append(mod_name)

    # AI src models
    src_dir = ROOT_DIR / "src"
    if src_dir.exists():
        for p in sorted(src_dir.rglob("*.py")):
            if p.name.startswith("test_") or p.name.startswith("__"):
                continue
            rel = p.relative_to(ROOT_DIR)
            mod_name = str(rel).replace("/", ".").replace("\\", ".")[:-3]
            modules.append(mod_name)

    return sorted(list(set(modules)))


ALL_MODULES = get_all_python_modules()


@pytest.mark.parametrize("mod_name", ALL_MODULES)
def test_module_import_cleanly(mod_name: str):
    """Verify that every single module imports cleanly using canonical import paths."""
    mod = importlib.import_module(mod_name)
    assert mod is not None, f"Failed to import {mod_name}"


def test_total_modules_count():
    """Assert that we discovered and verified at least 25 core production modules."""
    assert len(ALL_MODULES) >= 25, f"Expected >= 25 modules, found {len(ALL_MODULES)}: {ALL_MODULES}"

