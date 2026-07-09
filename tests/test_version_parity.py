"""The single source of truth for star's version must stay in sync.

pyproject.toml drives the wheel/sdist/PyPI version; star/_runtime.py's
``__version__`` (re-exported as ``APP_VERSION``) drives ``star --version``, the
About box, HTTP User-Agents, and — critically — the update checker's "am I
current?" comparison.  A release that bumps one but not the other makes the
installed app report the wrong number and nag every user of the NEW version to
"update" to the version they already have.  0.1.23 shipped that way in a draft;
this test makes the divergence impossible to miss.
"""
import re
import sys
from pathlib import Path

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _pyproject_version() -> str:
    text = _PYPROJECT.read_text(encoding="utf-8")
    if sys.version_info >= (3, 11):
        import tomllib

        return tomllib.loads(text)["project"]["version"]
    m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert m, "no version in pyproject.toml"
    return m.group(1)


def test_runtime_version_matches_pyproject():
    import star

    assert star.__version__ == _pyproject_version(), (
        "star.__version__ (star/_runtime.py) is out of sync with "
        "pyproject.toml — bump BOTH on every release."
    )


def test_app_version_is_the_runtime_version():
    from star._runtime import APP_VERSION, __version__

    assert APP_VERSION == __version__
