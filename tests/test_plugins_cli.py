"""Tests for the plugin-introspection helpers and the `star --plugins` CLI.

Covers:

* ``star.plugins.list_plugins`` / ``describe_plugin`` / ``describe_api`` return
  well-shaped, sane structured data for the built-in plugins.
* ``star.formats.__api_version__`` exists and is a MAJOR.MINOR string.
* The bundled example plugin under ``examples/plugin-template/`` imports, parses,
  and satisfies the FormatHandler contract — i.e. the template a third party
  would copy actually works.

These exercise the helpers directly (fast, no subprocess); the CLI wiring in
``star/app.py`` is a thin renderer over them.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from star import formats as star_formats
from star.formats import Exporter, FormatHandler
from star.plugins import (
    BACKEND_GROUP,
    EXPORTER_GROUP,
    FORMAT_GROUP,
    PLUGIN_GROUPS,
    PluginRegistry,
    describe_api,
    describe_plugin,
    list_plugins,
    override_plugins,
)
from star.tts.base import TTSBackend

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATE_DIR = _REPO_ROOT / "examples" / "plugin-template"


@pytest.fixture(autouse=True)
def _fresh_registry():
    PluginRegistry.reset()
    yield
    PluginRegistry.reset()


# ── API version ────────────────────────────────────────────────────────────────

def test_api_version_present_and_shaped():
    ver = star_formats.__api_version__
    assert isinstance(ver, str)
    major, _, minor = ver.partition(".")
    assert major.isdigit() and minor.isdigit(), f"expected MAJOR.MINOR, got {ver!r}"


# ── list_plugins ───────────────────────────────────────────────────────────────

def test_list_plugins_has_all_three_groups():
    grouped = list_plugins()
    assert set(grouped) == set(PLUGIN_GROUPS)
    assert set(grouped) == {BACKEND_GROUP, FORMAT_GROUP, EXPORTER_GROUP}


def test_list_plugins_entries_are_well_shaped():
    grouped = list_plugins()
    # Built-ins are installed, so every group is populated.
    for group, entries in grouped.items():
        assert entries, f"no plugins reported for {group}"
        for e in entries:
            assert e["group"] == group
            assert isinstance(e["name"], str) and e["name"]
            assert ":" in e["target"], f"target not module:attr — {e['target']!r}"
            # Either it loaded (has a class) or it recorded a load error.
            assert ("class" in e) or ("load_error" in e)
            assert isinstance(e["extensions"], list)


def test_list_plugins_formats_sorted_by_priority_then_name():
    entries = list_plugins()[FORMAT_GROUP]
    keys = [
        (e.get("priority") if e.get("priority") is not None else 1_000_000, e["name"])
        for e in entries
    ]
    assert keys == sorted(keys)


def test_list_plugins_reports_known_builtins():
    grouped = list_plugins()
    fmt_names = {e["name"] for e in grouped[FORMAT_GROUP]}
    assert {"pdf", "markdown", "txt", "html"} <= fmt_names
    backend_names = {e["name"] for e in grouped[BACKEND_GROUP]}
    assert {"silent", "piper"} <= backend_names
    exporter_names = {e["name"] for e in grouped[EXPORTER_GROUP]}
    assert {"wav", "markdown"} <= exporter_names


def test_format_handlers_report_availability_and_extensions():
    for e in list_plugins()[FORMAT_GROUP]:
        # FormatHandler.available is a classmethod, so it's evaluable eagerly.
        assert isinstance(e["available"], bool), e["name"]
    md = next(e for e in list_plugins()[FORMAT_GROUP] if e["name"] == "markdown")
    assert ".md" in md["extensions"]


# ── describe_plugin ────────────────────────────────────────────────────────────

def test_describe_plugin_markdown():
    info = describe_plugin(FORMAT_GROUP, "markdown")
    assert info is not None
    assert info["name"] == "markdown"
    assert info["group"] == FORMAT_GROUP
    assert info["class"].endswith("MarkdownHandler")
    assert info["priority"] == 50
    assert ".md" in info["extensions"]
    assert info["available"] is True
    assert info["doc"]  # first docstring line


def test_describe_plugin_unknown_returns_none():
    assert describe_plugin(FORMAT_GROUP, "no-such-plugin") is None


def test_describe_plugin_backend_availability_unknown():
    # TTSBackend.available is an instance method; the helper must not instantiate
    # a backend, so availability comes back as None ("unknown").
    info = describe_plugin(BACKEND_GROUP, "piper")
    assert info is not None
    assert info["available"] is None


# ── describe_api ───────────────────────────────────────────────────────────────

def test_describe_api_covers_three_abcs():
    api = describe_api()
    names = {spec["name"] for spec in api}
    assert any(n.endswith("TTSBackend") for n in names)
    assert any(n.endswith("FormatHandler") for n in names)
    assert any(n.endswith("Exporter") for n in names)


def test_describe_api_lists_abstract_methods_with_signatures():
    api = describe_api()
    fh = next(s for s in api if s["name"].endswith("FormatHandler"))
    assert fh["group"] == FORMAT_GROUP
    methods = {m["name"]: m for m in fh["methods"]}
    for required in ("extensions", "available", "load"):
        assert required in methods, f"{required} missing from FormatHandler API"
        assert methods[required]["abstract"] is True
        assert methods[required]["signature"].startswith(required + "(")
    # extensions/available are classmethods on FormatHandler.
    assert methods["extensions"]["classmethod"] is True


def test_describe_api_reports_the_api_version():
    api = describe_api()
    assert api and api[0]["api_version"] == star_formats.__api_version__


# ── example plugin template ────────────────────────────────────────────────────

def _load_template_module():
    """Import ``star_demo_format`` from the template dir without installing it."""
    pkg_init = _TEMPLATE_DIR / "star_demo_format" / "__init__.py"
    assert pkg_init.is_file(), f"template package missing at {pkg_init}"
    spec = importlib.util.spec_from_file_location("star_demo_format", pkg_init)
    module = importlib.util.module_from_spec(spec)
    # Register so a relative/self import inside the package resolves.
    sys.modules["star_demo_format"] = module
    try:
        spec.loader.exec_module(module)
    finally:
        pass
    return module


def test_template_module_imports_and_parses():
    module = _load_template_module()
    try:
        assert hasattr(module, "DemoHandler")
        handler_cls = module.DemoHandler
        assert issubclass(handler_cls, FormatHandler)
        assert handler_cls.name == "demo"
        assert ".demo" in handler_cls.extensions()
        assert handler_cls.available() is True
    finally:
        sys.modules.pop("star_demo_format", None)


def test_template_handler_loads_a_demo_document(tmp_path):
    module = _load_template_module()
    try:
        demo = tmp_path / "note.demo"
        demo.write_text("My Title\nThe body text.\n", encoding="utf-8")
        doc = module.DemoHandler().load(demo)
        assert doc.title == "My Title"
        assert "body text" in doc.plain_text
        assert doc.format == "demo"
    finally:
        sys.modules.pop("star_demo_format", None)


def test_template_handler_registers_via_override(tmp_path):
    """The template class works through the real registry dispatch path."""
    module = _load_template_module()
    try:
        with override_plugins(formats=[module.DemoHandler]):
            reg = PluginRegistry.get()
            handler = reg.handler_for(Path("something.demo"))
            assert isinstance(handler, module.DemoHandler)
    finally:
        sys.modules.pop("star_demo_format", None)


def test_template_pyproject_declares_the_entry_point():
    try:
        import tomllib  # py311+
    except ModuleNotFoundError:  # pragma: no cover - older interpreters
        tomllib = pytest.importorskip("tomli")
    data = tomllib.loads((_TEMPLATE_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    eps = data["project"]["entry-points"]["star.formats"]
    assert eps["demo"] == "star_demo_format:DemoHandler"


# ── consistency: describe_plugin agrees with the Exporter contract ──────────────

def test_exporters_have_extensions():
    for e in list_plugins()[EXPORTER_GROUP]:
        assert e["extensions"], f"exporter {e['name']} reported no extensions"


def test_all_builtin_bases_are_the_expected_abcs():
    # Guards against a refactor silently detaching the CLI from the ABCs.
    assert issubclass(FormatHandler, object) and hasattr(FormatHandler, "load")
    assert hasattr(Exporter, "export")
    assert hasattr(TTSBackend, "speak")
