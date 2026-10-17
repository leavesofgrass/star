"""The suite stays inside the checkout: nothing reaches the real star profile.

``tests/conftest.py`` points the home, profile and temp folders into pytest's
base temp folder before star is imported, gives every test its own star
profile, and refuses writes outside the checkout through an audit hook.  These
tests check each layer, and that the operations which used to write into the
real profile (settings, the document cache, themes, publish styles, the update
check, the font cache) now land in the test's own folder.

The guard tests raise audit events with ``sys.audit`` rather than performing
the operation, so even a broken guard writes nothing.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest


def _snapshot(folder):
    """Map every entry under *folder* to its (mtime_ns, size); {} if absent."""
    if folder is None or not os.path.isdir(folder):
        return {}
    entries = {}
    for dirpath, dirnames, filenames in os.walk(folder):
        for name in dirnames + filenames:
            path = os.path.join(dirpath, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            entries[path] = (st.st_mtime_ns, st.st_size)
    st = os.stat(folder)
    entries[str(folder)] = (st.st_mtime_ns, 0)
    return entries


def _inside(path, root) -> bool:
    path = os.path.normcase(os.path.abspath(os.fspath(path)))
    root = os.path.normcase(os.path.abspath(os.fspath(root)))
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def _outside_path() -> Path:
    """A path outside the checkout (no test ever creates it)."""
    return Path(os.path.abspath(os.sep)) / "star-isolation-probe" / "probe.txt"


# ── the folders ──────────────────────────────────────────────────────────────


def test_base_temp_folder_is_not_the_system_temp(tmp_path_factory, pytestconfig, real_env):
    base = tmp_path_factory.getbasetemp()
    given = pytestconfig.option.basetemp
    if given is None or not os.path.isabs(str(given)):
        # pyproject.toml's --basetemp=build/pytest-tmp, inside the checkout.
        assert _inside(base, pytestconfig.rootpath)
    real_temps = [real_env.get(k) for k in ("TMP", "TEMP", "TMPDIR")]
    if os.name != "nt":
        real_temps.append("/tmp")
    for temp in filter(None, real_temps):
        assert not _inside(base, temp), f"base temp {base} is in the system temp {temp}"


def test_home_profile_and_temp_point_into_this_test(tmp_path, tmp_path_factory):
    home = tmp_path / "test-home"
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME",
                "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        assert _inside(os.environ[key], home), key
    assert _inside(Path.home(), home)
    assert _inside(tempfile.gettempdir(), tmp_path_factory.getbasetemp())


def test_star_profile_paths_point_into_this_test(tmp_path):
    import star._runtime as runtime
    import star.cache as cache
    import star.fulltext as fulltext
    import star.publish as publish
    import star.settings as settings_mod
    import star.themes as themes
    import star.tts.eloquence as eloquence
    import star.update as update

    profile = tmp_path / "test-profile"
    assert Path(runtime._CFG_ROOT) == profile
    assert settings_mod.SETTINGS_FILE == profile / "settings.json"
    assert Path(cache.CACHE_DIR) == profile / "cache"
    assert themes.THEMES_DIR == profile / "themes"
    assert publish.PUBLISH_STYLES_DIR == profile / "publish-styles"
    assert runtime.LOG_FILE == profile / "star.log"
    # Paths star derives from the profile at import time move with it.
    assert eloquence.ELOQUENCE_DIR == profile / "eloquence"
    assert _inside(fulltext._INDEX_CACHE, profile)
    assert _inside(update._CACHE_FILE, profile)


def test_real_profile_untouched_by_profile_writes(tmp_path, real_star_profile):
    """Every write star makes to its profile lands in the test's folder."""
    import star.cache as cache
    import star.fonts as fonts
    import star.publish as publish
    import star.themes as themes
    import star.update as update
    from star.settings import Settings

    before = _snapshot(real_star_profile)

    settings = Settings()
    settings["theme"] = "dark"  # saves settings.json
    themes._seed_default_css_themes()
    publish._seed_user_styles()
    doc = tmp_path / "doc.md"
    doc.write_text("word " * 400, encoding="utf-8")  # over the 1 KB cache floor
    cache._cache_save(str(doc), {"plain_text": "word"}, "fingerprint")
    update._write_cache(update._CACHE_FILE, "9.9.9")
    fonts.font_dir()

    profile = tmp_path / "test-profile"
    assert (profile / "settings.json").is_file()
    assert any((profile / "themes").glob("*.css"))
    assert any((profile / "publish-styles").iterdir())
    assert any(p.name != "fonts" for p in (profile / "cache").iterdir())
    assert Path(update._CACHE_FILE).is_file()
    assert (profile / "cache" / "fonts").is_dir()
    assert _snapshot(real_star_profile) == before


def test_each_test_gets_a_fresh_profile_part_one(tmp_path):
    from star.settings import Settings

    Settings()["theme"] = "solarized-light"
    assert (tmp_path / "test-profile" / "settings.json").is_file()


def test_each_test_gets_a_fresh_profile_part_two(tmp_path):
    from star.settings import DEFAULTS, Settings

    # Whatever order xdist runs these in, this test sees no saved settings.
    assert not (tmp_path / "test-profile" / "settings.json").exists()
    assert Settings().get("theme") == DEFAULTS["theme"]


# ── the guard ────────────────────────────────────────────────────────────────


@pytest.fixture
def guard(isolation_guard):
    if not isolation_guard.active:
        pytest.skip("the isolation guard is switched off (STAR_TEST_GUARD=0)")
    return isolation_guard


def test_write_outside_the_checkout_is_refused(guard, real_star_profile):
    targets = [_outside_path()]
    if real_star_profile is not None:
        targets.append(real_star_profile / "settings.json")
    for target in targets:
        with guard.expect_refusals() as refused:
            with pytest.raises(PermissionError):
                sys.audit("open", str(target), "w", os.O_WRONLY | os.O_CREAT)
        assert len(refused) == 1 and str(target).lower() in refused[0].lower()


def test_create_rename_and_delete_outside_are_refused(guard, tmp_path):
    outside = str(_outside_path())
    inside = str(tmp_path / "file.txt")
    events = [
        ("os.mkdir", (outside, 0o777, None)),
        ("os.replace", (inside, outside, None, None)),
        ("os.rename", (outside, inside, None, None)),
        ("os.remove", (outside, None)),
        ("os.rmdir", (outside, None)),
        ("shutil.rmtree", (outside, None)),
        ("shutil.copyfile", (inside, outside)),
        ("tempfile.mkdtemp", (outside,)),
        ("sqlite3.connect", (outside,)),
    ]
    for event, args in events:
        with guard.expect_refusals() as refused:
            with pytest.raises(PermissionError):
                sys.audit(event, *args)
        assert len(refused) == 1, event


def test_reads_and_writes_inside_the_checkout_pass(guard, tmp_path):
    with guard.expect_refusals() as refused:
        sys.audit("open", str(tmp_path / "x.txt"), "w", os.O_WRONLY | os.O_CREAT)
        sys.audit("open", str(_outside_path()), "r", os.O_RDONLY)  # reading is fine
        sys.audit("open", os.devnull, "w", os.O_WRONLY)
        sys.audit("os.mkdir", str(tmp_path / "sub"), 0o777, None)
        sys.audit("sqlite3.connect", ":memory:")
        (tmp_path / "real.txt").write_text("written", encoding="utf-8")
    assert refused == []


def test_bytecode_caches_outside_are_refused_quietly(guard):
    pyc = _outside_path().parent / "__pycache__" / "mod.cpython-313.pyc.12345"
    with guard.expect_refusals() as refused:
        with pytest.raises(PermissionError):
            sys.audit("open", str(pyc), None, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    assert refused == []  # the import system skips the cache; no test fails
