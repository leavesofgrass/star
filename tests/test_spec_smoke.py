"""star.spec must remain valid Python.

The PyInstaller spec is executed as Python by PyInstaller, but it can only be
*built* on the target OS (the darwin/`.app` vs Windows/exe branch means the
whole thing is never exercised off-Mac in CI).  A stray syntax error in the
untaken branch would therefore ship silently until a release build on that OS.
This ast.parse smoke test guards the file's syntax on every platform.
"""
import ast
import pathlib


def test_star_spec_parses_as_python():
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    spec = repo_root / "star.spec"
    assert spec.is_file(), f"star.spec not found at {spec}"
    source = spec.read_text(encoding="utf-8")
    ast.parse(source, filename=str(spec))  # raises SyntaxError on regression
