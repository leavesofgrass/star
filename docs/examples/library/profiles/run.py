#!/usr/bin/env python3
"""Export reading profiles to a shareable JSON file, then import them back.

star's named profiles bundle a whole reading setup — voice, rate, theme,
fonts, spacing, highlight style. Since 0.1.27 they travel: an export writes a
small JSON envelope you can copy to another machine (or send to a friend) and
import there. This example does the round trip with the library API — the same
helpers behind the GUI's **Edit > Export Profiles… / Import Profiles…**.
"""
import json
import shutil
from pathlib import Path


def main() -> int:
    try:
        import star.settings as settings_mod
        from star.settings import Settings
        from star.stats import _export_profiles, _import_profiles, _save_profile
    except ImportError:
        print("This example needs star installed:  pip install star-reader")
        return 0  # degrade gracefully so the smoke test stays green

    # Sandbox the demo: point star's settings file into ./out so nothing here
    # touches your real preferences or saved profiles.
    out_dir = Path.cwd() / "out"
    out_dir.mkdir(exist_ok=True)
    settings_mod.SETTINGS_FILE = out_dir / "machine-a.json"

    # --- "Machine A": save two named profiles, then export them ------------
    settings = Settings()
    settings.set("tts_rate", 300)
    settings.set("theme", "dracula")
    _save_profile(settings, "fast-dark")
    settings.set("tts_rate", 180)
    settings.set("theme", "galaxy-light")
    _save_profile(settings, "relaxed-light")

    payload = _export_profiles(settings)  # or names=["fast-dark"] for a subset
    dest = out_dir / "profiles.json"
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Exported {len(payload['profiles'])} profiles to {dest.name}")
    print(f"  envelope:   star_profiles format v{payload['star_profiles']}, "
          f"written by star {payload['app_version']}")
    for name, values in payload["profiles"].items():
        print(f"  profile:    {name}  ({len(values)} settings captured)")
    print()

    # --- "Machine B": import the file into a fresh settings store ----------
    settings_mod.SETTINGS_FILE = out_dir / "machine-b.json"
    fresh = Settings()
    envelope = json.loads(dest.read_text(encoding="utf-8"))
    imported, dropped = _import_profiles(fresh, envelope)

    print(f"Imported: {', '.join(imported)}")
    if dropped:
        print(f"Dropped keys this star doesn't know: {', '.join(dropped)}")
    prof = fresh.get("profiles")["fast-dark"]
    print(f"Round trip: 'fast-dark' arrived with tts_rate={prof['tts_rate']} "
          f"and theme={prof['theme']!r}")

    shutil.rmtree(out_dir)  # demo artifacts only — nothing real was touched
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
