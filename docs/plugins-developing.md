# 🔌 Developing star plugins

`star` is extensible through **entry-point plugins**: a separate pip package can
add a TTS voice engine, teach star a new document format, or add an export
target — with no fork and no change to star itself. star discovers your plugin at
runtime through Python's standard `importlib.metadata` entry-points, exactly the
way its own built-ins are registered.

- [The three plugin groups](#the-three-plugin-groups)
- [The plugin API contract](#the-plugin-api-contract)
- [Format handlers](#format-handlers-starformats)
- [TTS backends](#tts-backends-starbackends)
- [Exporters](#exporters-starexporters)
- [Packaging as a pip distribution](#packaging-as-a-pip-distribution)
- [Testing a plugin locally](#testing-a-plugin-locally)
- [Introspecting the plugin system](#introspecting-the-plugin-system)

There is a complete, working, copy-me example in
[`examples/plugin-template/`](../examples/plugin-template/) — a ~40-line package
that adds a toy `.demo` format. Read this guide, then start from that template.

---

## The three plugin groups

Every plugin is a class that subclasses one of star's three abstract base classes
(ABCs) and is registered in the matching entry-point group:

| Entry-point group | Base class (ABC) | What it adds |
|-------------------|------------------|--------------|
| `star.formats`    | `star.formats.FormatHandler`  | A document loader for one or more file extensions |
| `star.backends`   | `star.tts.base.TTSBackend`    | A text-to-speech engine |
| `star.exporters`  | `star.formats.Exporter`       | An export target (a new output format) |

Registration is one table in your package's `pyproject.toml`. The key is the
**plugin name** (shown by `star --plugins list`); the value is `module:ClassName`:

```toml
[project.entry-points."star.formats"]
demo = "star_demo_format:DemoHandler"
```

At runtime `star.plugins.PluginRegistry` loads every entry-point in each group,
verifies it subclasses the right ABC, and caches it. Discovery is automatic —
installing your package next to star is all it takes.

---

## The plugin API contract

The ABCs in `star/formats.py` (and `star/tts/base.py`) are versioned by
**`star.formats.__api_version__`** (currently `"1.0"`), using `MAJOR.MINOR`:

- **MAJOR** bumps on a breaking change to an ABC — a renamed/removed method or a
  changed required signature. A plugin built for a different major version may
  fail to load.
- **MINOR** bumps for backward-compatible additions — a new optional method with
  a default, or a new keyword argument.

This is deliberately **decoupled from the star release version** (`star.__version__`),
which changes far more often. Pin your plugin against the API, not the release:

```python
from star import formats

_MAJOR = int(formats.__api_version__.split(".")[0])
if _MAJOR != 1:
    raise ImportError(
        f"this plugin targets star plugin API 1.x, host has {formats.__api_version__}"
    )
```

In your package metadata, a broad floor on star itself (e.g.
`star-reader>=0.1.16`, the release that introduced the plugin system) is usually
the right dependency; add an optional runtime check like the above only if you
need to fail loudly on an incompatible host.

Inspect the live contracts any time with **`star --plugins api`**.

---

## Format handlers (`star.formats`)

A `FormatHandler` turns a file on disk into a `star.documents.Document`. Two
class methods declare *which files it handles* and *whether it can run*; one
instance method does the loading.

```python
from pathlib import Path
from star.formats import FormatHandler


class DemoHandler(FormatHandler):
    name = "demo"        # must match the entry-point key
    priority = 100       # lower = preferred; see note below

    @classmethod
    def extensions(cls) -> frozenset[str]:
        # lowercase, each including the leading dot
        return frozenset({".demo"})

    @classmethod
    def available(cls) -> bool:
        # probe optional deps here; return False if they're missing
        return True

    def load(self, path: Path, **kwargs):
        from star.documents import Document          # lazy: keeps import cheap
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        doc = Document()
        doc.path = str(path)
        doc.title = path.stem
        doc.format = "demo"
        doc.markdown = text        # feeds the on-screen view
        doc.plain_text = text      # feeds TTS
        return doc
```

The `Document` fields that matter most: `markdown` (rendered view), `plain_text`
(what TTS reads), `title`, `format`, and optionally `metadata` and `chapters`.

**Priority.** When two handlers claim the same extension, star uses the one with
the **lowest** `priority` whose `available()` is `True`. Built-ins use 10–50, so
third-party handlers should use **≥ 100** — unless you deliberately want to
override a built-in for a shared extension, in which case pick a lower number.

**`available()`.** Keep it cheap and side-effect-free — probe with
`importlib.util.find_spec("mylib")` rather than importing. It lets
`star --plugins list` mark your handler unavailable instead of crashing when a
file is opened without the optional dependency installed.

---

## TTS backends (`star.backends`)

A `TTSBackend` is a speech engine. Only `available`, `speak`, and `stop` are
required; the rest have safe no-op defaults, so override only what you support.

```python
from star.tts.base import TTSBackend


class MyBackend(TTSBackend):
    name = "mybackend"   # must match the entry-point key
    priority = 100       # auto-selection order; lower = tried first

    def available(self) -> bool:
        return True       # is the engine usable right now?

    def speak(self, text, on_word=None, on_done=None):
        # synthesize + play `text`.  Call on_word(start, length) as each word is
        # spoken to drive the reading highlight; call on_done() when finished.
        ...
        if on_done:
            on_done()

    def stop(self):
        ...               # halt any in-progress speech
```

Optional overrides: `set_rate(wpm)`, `set_volume(vol)`, `set_voice(voice_id)`,
`list_voices()`, `export_to_wav(text, wav_path)`, and the `speaking` property.

Note `available()` is an **instance** method on `TTSBackend` (unlike the
classmethod on `FormatHandler`), because deciding whether an engine is usable can
require constructing it. star selects a backend by trying registered classes in
`priority` order and picking the first whose `available()` returns `True`.
Built-in backends use 10–90; third-party backends should use **≥ 100**.

---

## Exporters (`star.exporters`)

An `Exporter` writes a `Document` out in a new format.

```python
from pathlib import Path
from star.formats import Exporter


class MyExporter(Exporter):
    name = "myfmt"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".myfmt"})

    @classmethod
    def available(cls) -> bool:
        return True

    def export(self, document, path: Path, **kwargs) -> None:
        Path(path).write_text(document.plain_text, encoding="utf-8")
```

---

## Packaging as a pip distribution

A plugin is an ordinary Python package. The only star-specific part is the
entry-point table. Minimal `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "star-demo-format"
version = "0.1.0"
description = "Example star plugin: a FormatHandler for the .demo format"
requires-python = ">=3.9"
dependencies = ["star-reader>=0.1.16"]

[project.entry-points."star.formats"]
demo = "star_demo_format:DemoHandler"

[tool.setuptools]
packages = ["star_demo_format"]
```

Notes:

- **Quote the group name.** TOML needs `"star.formats"` in quotes because of the
  dot.
- **Import cheaply.** Import `star.formats` / `star.tts.base` at module top —
  those hold only the ABCs. Defer heavy imports (`star.documents`, your engine's
  library) into the methods that need them, so merely *declaring* the plugin
  doesn't slow star's startup.
- Publish to PyPI like any package (`python -m build`, `twine upload`); users then
  `pip install your-plugin` into the same environment as star.

---

## Testing a plugin locally

Install the plugin editable, next to star, and let entry-point discovery do the
rest:

```bash
cd examples/plugin-template
pip install -e .

star --plugins list                    # your plugin appears in its group
star --plugins info formats demo        # its details
```

Then exercise it end to end:

```bash
printf 'My Title\nBody text.\n' > note.demo
star --plain note.demo                  # routes through your handler
```

For a unit test, drive the registry directly without any install using the
`override_plugins` context manager — it swaps in your class for the duration of a
`with` block and restores the real registry on exit:

```python
from pathlib import Path
from star.plugins import PluginRegistry, override_plugins
from star_demo_format import DemoHandler

def test_demo_handler_registers():
    with override_plugins(formats=[DemoHandler]):
        reg = PluginRegistry.get()
        handler = reg.handler_for(Path("note.demo"))
        assert isinstance(handler, DemoHandler)
```

`override_plugins` accepts `backends=`, `formats=`, and `exporters=` lists; see
`tests/test_plugins.py` in the star repo for more patterns.

---

## Introspecting the plugin system

The `star --plugins` CLI reports the live plugin state — useful both when
developing a plugin and when diagnosing why one isn't loading:

| Command | Shows |
|---------|-------|
| `star --plugins list` | Every registered plugin, by group, with target, priority, extensions, and availability |
| `star --plugins info <group> <name>` | One plugin's full details (`<group>` is `backends`, `formats`, or `exporters`) |
| `star --plugins api`  | The ABC contracts — every method you implement, with signatures and which are abstract |

If your plugin doesn't appear in `list`, it wasn't discovered: check that the
package is installed in the same environment, that the entry-point group name is
quoted correctly, and that the `module:ClassName` target resolves. A plugin that
is found but fails to import shows a `load error` line rather than being dropped
silently.
