"""Tests for the $PATH fallback behaviour of sfp_tool_* modules.

The strict tool modules used to bail out with an error whenever the
user left the per-tool ``<tool>_path`` UI field blank. After the patch
they should fall back to ``shutil.which()`` to discover the binary on
``$PATH`` and only error if neither source resolves a real file.

These tests exercise the small ``_resolve_binary()`` helper that each
patched module exposes — they avoid running ``setup()`` (which can be
heavy in the async plugin base class) by constructing a bare instance
and assigning ``self.opts`` directly.
"""

from __future__ import annotations

import importlib
import os

import pytest


# (module_name, class_name, opt_key, binary_name)
#
# ``binary_name`` is the file we expect ``shutil.which`` to return —
# it's not always identical to the prefix of ``opt_key`` (retirejs vs.
# ``retire``, cmseekpath vs. ``cmseek.py``, etc.).
STRICT_MODULES = [
    ("modules.sfp_tool_nbtscan", "sfp_tool_nbtscan", "nbtscan_path", "nbtscan"),
    ("modules.sfp_tool_onesixtyone", "sfp_tool_onesixtyone", "onesixtyone_path", "onesixtyone"),
    ("modules.sfp_tool_retirejs", "sfp_tool_retirejs", "retirejs_path", "retire"),
    ("modules.sfp_tool_snallygaster", "sfp_tool_snallygaster", "snallygaster_path", "snallygaster"),
    ("modules.sfp_tool_testsslsh", "sfp_tool_testsslsh", "testsslsh_path", "testssl.sh"),
    ("modules.sfp_tool_trufflehog", "sfp_tool_trufflehog", "trufflehog_path", "trufflehog"),
    ("modules.sfp_tool_wafw00f", "sfp_tool_wafw00f", "wafw00f_path", "wafw00f"),
    ("modules.sfp_tool_whatweb", "sfp_tool_whatweb", "whatweb_path", "whatweb"),
    ("modules.sfp_tool_gobuster", "sfp_tool_gobuster", "gobuster_path", "gobuster"),
    # cmseek is special: it ships as ``cmseek.py`` and uses ``cmseekpath``.
    ("modules.sfp_tool_cmseek", "sfp_tool_cmseek", "cmseekpath", "cmseek"),
    ("modules.sfp_tool_maigret", "sfp_tool_maigret", "maigret_path", "maigret"),
    ("modules.sfp_tool_ghunt", "sfp_tool_ghunt", "ghunt_path", "ghunt"),
    ("modules.sfp_tool_holehe", "sfp_tool_holehe", "holehe_path", "holehe"),
    ("modules.sfp_tool_sherlock", "sfp_tool_sherlock", "sherlock_path", "sherlock"),
]


def _make_instance(module_path, class_name):
    """Return a bare instance with ``opts`` patched on.

    We intentionally bypass ``setup()`` — these tests only care about
    the binary resolution helper, which reads ``self.opts``.
    """
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    inst = cls.__new__(cls)
    # Start from the class-level defaults so every option key the
    # helper might read is present.
    inst.opts = dict(getattr(cls, "opts", {}) or {})
    return mod, inst


@pytest.mark.parametrize(
    "module_path,class_name,opt_key,binary",
    STRICT_MODULES,
    ids=[m[1] for m in STRICT_MODULES],
)
def test_blank_opt_falls_back_to_path(monkeypatch, module_path, class_name, opt_key, binary):
    """Blank ``<tool>_path`` should resolve via ``shutil.which``."""
    mod, inst = _make_instance(module_path, class_name)
    inst.opts[opt_key] = ""

    fake = f"/fake/path/{binary}"
    monkeypatch.setattr(mod.shutil, "which", lambda name: fake if name == binary else None)

    result = inst._resolve_binary()

    # cmseek returns a tuple (exe, resultpath); everything else is a str.
    if isinstance(result, tuple):
        exe, _ = result
    else:
        exe = result

    assert exe == fake, (
        f"{class_name}._resolve_binary() should fall back to "
        f"shutil.which({binary!r}) when {opt_key!r} is blank, got {exe!r}"
    )


@pytest.mark.parametrize(
    "module_path,class_name,opt_key,binary",
    STRICT_MODULES,
    ids=[m[1] for m in STRICT_MODULES],
)
def test_explicit_path_is_preferred_over_which(monkeypatch, tmp_path, module_path, class_name, opt_key, binary):
    """An explicit (existing) ``<tool>_path`` wins over ``shutil.which``."""
    mod, inst = _make_instance(module_path, class_name)

    # cmseek wants a file literally named cmseek.py.
    if class_name == "sfp_tool_cmseek":
        real = tmp_path / "cmseek.py"
    else:
        real = tmp_path / binary
    real.write_text("#!/bin/sh\nexit 0\n")
    os.chmod(real, 0o755)

    inst.opts[opt_key] = str(real)

    # shutil.which would return a different path if consulted — we
    # assert it isn't.
    monkeypatch.setattr(mod.shutil, "which", lambda name: "/should/not/be/used")

    result = inst._resolve_binary()
    if isinstance(result, tuple):
        exe, _ = result
    else:
        exe = result

    assert exe == str(real), (
        f"{class_name}._resolve_binary() must prefer an explicit existing "
        f"{opt_key!r} over shutil.which()"
    )


@pytest.mark.parametrize(
    "module_path,class_name,opt_key,binary",
    STRICT_MODULES,
    ids=[m[1] for m in STRICT_MODULES],
)
def test_blank_opt_and_not_on_path_returns_none(monkeypatch, module_path, class_name, opt_key, binary):
    """If both sources fail, the helper must return None (not raise)."""
    mod, inst = _make_instance(module_path, class_name)
    inst.opts[opt_key] = ""

    monkeypatch.setattr(mod.shutil, "which", lambda name: None)

    result = inst._resolve_binary()
    if isinstance(result, tuple):
        exe, _ = result
    else:
        exe = result

    assert exe is None, (
        f"{class_name}._resolve_binary() must return None when {opt_key!r} "
        f"is blank and {binary!r} is not on $PATH"
    )
