# star-demo-format — an example star plugin

A minimal, real, pip-installable third-party plugin for
[**star**](https://pypi.org/project/star-reader/). It teaches star a toy
`.demo` document format by registering a `FormatHandler` in the `star.formats`
entry-point group.

Use it as a **template**: copy the directory, rename the package, and swap the
handler class for your own.

## What's here

```
plugin-template/
├── pyproject.toml            # package metadata + the entry-point declaration
├── README.md                 # this file
└── star_demo_format/
    └── __init__.py           # the DemoHandler class
```

The whole plugin is ~40 lines. The two load-bearing pieces are:

1. A class that subclasses one of star's plugin ABCs
   (`FormatHandler` / `star.tts.base.TTSBackend` / `Exporter`).
2. An entry-point in `pyproject.toml` that points star's registry at it:

   ```toml
   [project.entry-points."star.formats"]
   demo = "star_demo_format:DemoHandler"
   ```

## Try it

From this directory, with star already installed in the same environment:

```bash
pip install .            # or: pip install -e .   for an editable install

star --plugins list      # DemoHandler shows up under the star.formats group
star --plugins info formats demo

printf 'My Title\nThe body of the demo file.\n' > note.demo
star --plain note.demo   # extracts:  My Title. The body of the demo file.
```

Open `note.demo` in the GUI or TUI and star routes it through `DemoHandler`
automatically — no wiring beyond the entry-point.

## Next steps

- Read the full guide: **`docs/plugins-developing.md`** in the star repository.
- Inspect the contracts you implement against: `star --plugins api`.
- For a TTS engine, subclass `star.tts.base.TTSBackend` and register under
  `[project.entry-points."star.backends"]`; for an export target, subclass
  `star.formats.Exporter` and register under `[project.entry-points."star.exporters"]`.

## License

Public-domain example — copy freely.
