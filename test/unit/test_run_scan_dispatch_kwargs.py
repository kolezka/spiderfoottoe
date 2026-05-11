"""Regression tests for run_scan task dispatch kwargs.

Guards against the rerun bug where call sites used the wrong kwarg names
(``scan_target`` / ``type_list``) and omitted required parameters
(``scan_id`` / ``target_type``), causing Celery dispatch to fail with
``TypeError: run_scan() got an unexpected keyword argument 'scan_target'``
and silently fall back to a broken ``mp.Process`` path that made scans
"end quickly".

These tests assert that:
1. The task signature declares the exact parameter names every dispatcher
   in the codebase must use.
2. Every dispatch site in ``spiderfoot/api/routers/scan.py`` builds a
   ``kwargs={...}`` dict whose keys are a subset of those parameter names
   and includes all six required parameters.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from spiderfoot.tasks.scan import run_scan


REQUIRED_PARAMS = {
    "scan_name", "scan_id", "target_value", "target_type",
    "module_list", "global_opts",
}
OPTIONAL_PARAMS = {"engine_name", "stealth_level"}


def test_run_scan_signature_declares_expected_params():
    sig = inspect.signature(run_scan)
    params = set(sig.parameters) - {"self"}
    assert REQUIRED_PARAMS.issubset(params), (
        f"run_scan signature missing required params: {REQUIRED_PARAMS - params}"
    )
    assert params <= REQUIRED_PARAMS | OPTIONAL_PARAMS, (
        f"run_scan signature has unexpected params: "
        f"{params - REQUIRED_PARAMS - OPTIONAL_PARAMS}"
    )


def _extract_run_scan_dispatch_kwargs(source_path: Path) -> list[set[str]]:
    """Return the kwargs-dict keysets of every ``run_scan.apply_async`` call.

    Walks the AST so the check stays accurate even if the formatting changes.
    Only inspects calls whose attribute chain ends in
    ``run_scan.apply_async`` and that pass a ``kwargs=`` keyword whose value
    is a dict literal.
    """
    tree = ast.parse(source_path.read_text())
    found: list[set[str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "apply_async"):
            continue
        if not (isinstance(func.value, ast.Name) and func.value.id == "run_scan"):
            continue
        for kw in node.keywords:
            if kw.arg == "kwargs" and isinstance(kw.value, ast.Dict):
                keys = {
                    k.value for k in kw.value.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)
                }
                found.append(keys)
    return found


@pytest.mark.parametrize(
    "rel_path",
    [
        "spiderfoot/api/routers/scan.py",
        "spiderfoot/api/routers/schedules.py",
        "spiderfoot/tasks/monitor.py",
    ],
)
def test_api_router_dispatch_sites_use_correct_kwargs(rel_path: str):
    repo_root = Path(__file__).resolve().parents[2]
    source = repo_root / rel_path
    kwarg_sets = _extract_run_scan_dispatch_kwargs(source)
    assert kwarg_sets, f"No run_scan.apply_async calls found in {rel_path}"
    for keys in kwarg_sets:
        unknown = keys - (REQUIRED_PARAMS | OPTIONAL_PARAMS)
        missing = REQUIRED_PARAMS - keys
        assert not unknown, (
            f"{rel_path}: run_scan.apply_async passes unknown kwargs {unknown}"
        )
        assert not missing, (
            f"{rel_path}: run_scan.apply_async missing required kwargs {missing}"
        )
