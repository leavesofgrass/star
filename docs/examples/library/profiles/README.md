# Share reading profiles between machines

A named profile bundles a whole reading setup — voice, rate, theme, fonts,
spacing, and highlight style. Since 0.1.27 profiles travel: exporting writes a
small JSON envelope you can copy to another machine (or send to a friend) and
import there, even across star versions. This example does the full round trip
in Python with the library API — the same helpers behind the GUI's
**Edit > Export Profiles… / Import Profiles…**.

**You'll need:** nothing beyond `star-reader`. The demo sandboxes itself under
`./out/`, so your real settings and saved profiles are never touched.

## Run it

    cd docs/examples/library/profiles
    python run.py

## What you should see

    Exported 2 profiles to profiles.json
      envelope:   star_profiles format v1, written by star 0.1.27
      profile:    fast-dark  (20 settings captured)
      profile:    relaxed-light  (20 settings captured)

    Imported: fast-dark, relaxed-light
    Round trip: 'fast-dark' arrived with tts_rate=300 and theme='dracula'

(The app version and captured-settings count track your installed star.)

## How it works

- The script first rebinds `star.settings.SETTINGS_FILE` into `./out/` so the
  demo reads and writes a scratch settings store, not your real one.
- `_save_profile(settings, name)` (from `star.stats`) captures the current
  values of the profile keys — the same list both UIs save.
- `_export_profiles(settings)` builds the shareable envelope:
  `{"star_profiles": 1, "app_version": "...", "profiles": {...}}`. The format
  marker and writing version are what let imports stay honest across releases;
  pass `names=[...]` to export a subset.
- `_import_profiles(settings, payload)` merges the envelope into a settings
  store — here a **fresh** `Settings()` pointed at a second file, playing the
  role of another machine. It returns `(imported_names, dropped_keys)`: keys
  this star version doesn't know (from a newer or older release) are dropped
  and reported, legacy theme names are resolved, and same-name profiles are
  overwritten. A file that isn't a profile export raises `ValueError`.
- The `out/` directory is cleaned up after the demo.

## Next steps

- In the app: save a profile with **Edit > Save Current Settings as Profile…**
  (Ctrl+Shift+K), then **Edit > Export Profiles…** to write the same JSON.
- [Configuration reference](../../../configuration.md) — every setting a
  profile can carry.
- [`../load-a-document`](../load-a-document) — the library API's other entry
  point: documents instead of settings.
