# Linux development container

star is developed on Windows and runs on Linux too. The Docker container runs the test suite on Linux on a Windows machine, with the Linux speech engines installed, so the Linux checks need not wait for CI.

## What is in the image

`docker/Dockerfile` builds `star-dev:latest`, one image shared by every worktree and agent:

- **Debian trixie** with its **Python 3.13** (3.13.5), in a virtual environment at `/opt/venv`.
- **star's Python packages:** the base dependencies plus the `all` and `test` extras from `pyproject.toml`, and an editable install of star itself, so the plugin registry finds star's entry points.
- **Speech:** espeak-ng (1.52.0) and speech-dispatcher.
- **Documents and media:** pandoc and ffmpeg.
- **Qt runtime:** the libraries the CI job installs (libegl1, libgl1, libxkbcommon0, libdbus-1-3, libxcb-cursor0), plus GLib, fontconfig, FreeType and the DejaVu fonts, which a GitHub runner already has. Qt runs on its offscreen platform (`QT_QPA_PLATFORM=offscreen`).

Left out on purpose:

- **`louis` from PyPI.** The PyPI package of that name is an unrelated placeholder, not liblouis's Python bindings, so the image does not install it. The Braille translation tests skip in the container, as they do in CI.
- **spaCy and its language model** (the `ner` extra). The knowledge graph uses its regex fallback.
- **A sound device.** Tests never open one.

The checkout is not copied into the image. It is mounted at `/work` when the container runs, so the code under test is always the worktree's own.

## Build the image

Run this from the repository root. Before a build, check that drive D: keeps at least 200 GB free and the machine at least 20 GB of free memory, and look at Docker's disk use with `docker system df`.

```bash
docker compose build dev
```

Rebuild after `pyproject.toml` changes: a new dependency or a new entry point (backend, format, exporter) reaches the image only through a rebuild. Only a change to the dependency list re-runs the slow package install.

## Run the test suite

```bash
docker compose run --rm -T dev bash tools/ci-pytest.sh python -m pytest
```

This runs the whole suite as CI does, inside a fresh container, and `--rm` discards the container when it ends. The `-T` flag is for scripts and agents; leave it out at a terminal.

An interactive shell in `/work`, also discarded on exit:

```bash
docker compose run --rm dev
```

Then, inside it, run the suite with `bash tools/ci-pytest.sh python -m pytest`, or one file with `python -m pytest tests/test_tts.py -n0`.

In Git Bash, put `MSYS_NO_PATHCONV=1` before any `docker` command, so Git Bash does not rewrite container paths such as `/work` into Windows paths.

## Where the container writes

- **`/work`** is the checkout, mounted read-write. The suite writes nothing there from the container.
- **`/target`** is a named volume of the container's own: pytest's temp folder (`/target/pytest-tmp`) and cache (`/target/pytest-cache`), Python bytecode (`/target/pycache`), the Hypothesis database (`/target/hypothesis`) and the test wrapper's logs (`/target/tmp`). The variables that put them there are in `compose.yaml`. Linux files never mix with the Windows checkout.

## Parallel agents

Each agent works in its own git worktree, runs the container from that worktree's root, and names its own volume with `STAR_AGENT`:

```bash
STAR_AGENT=w1a MSYS_NO_PATHCONV=1 docker compose run --rm -T dev bash tools/ci-pytest.sh python -m pytest
```

The volume is called `star-target-<agent>` (`star-target-orch` by default). Each container gets 6 GB of memory and 4 CPUs by default, and pytest starts one worker per CPU; change them with `STAR_MEM` and `STAR_CPUS`.

## Test isolation and the network

The suite keeps every write inside the checkout, natively and in the container:

- pytest's temp folder is `build/pytest-tmp` in the checkout (`--basetemp` in `pyproject.toml`), never the system temp folder.
- `tests/conftest.py` points HOME, APPDATA, the XDG folders and the temp variables into that folder before star is imported, and gives each test its own star profile, so no test reads or writes the real one.
- An audit hook in `tests/conftest.py` refuses any write outside the checkout, its temp folder and the Python environment, and fails the test that tried it. It also refuses network access to any test not marked `network`. Set `STAR_TEST_GUARD=0` only to debug the guard itself.

pytest opens its output-capture files before `tests/conftest.py` runs, so `tools/ci-pytest.sh` points `TMPDIR`, `TMP` and `TEMP` at `build/tmp` before it starts pytest (in the container, at `/target/tmp`). Run full suites through it. A bare `python -m pytest` on Windows still puts those two short-lived files in the system temp folder.

Tests marked `network` are deselected by default. Run them on purpose with:

```bash
python -m pytest -m network -n0
```

Each sends only a public identifier (an ISBN) with star's own User-Agent, and skips when the service cannot be reached. CI runs them in the full-fat job only.

## Volumes and disk

The image and the volumes stay until someone removes them. Removing a volume or an image is a delete: check with the project maintainer first, list exactly what goes, and remove only what your own work created. Never prune Docker's data: other projects keep licensed engines and images there.

List star's volumes:

```bash
docker volume ls --filter name=star-target-
```

## Results

Measured when the image was first built, on Saturday, October 17, 2026:

- **Image:** `star-dev:latest`, 2.65 GB. Python 3.13.5, eSpeak NG 1.52.0, pandoc 3.1.11.1, FFmpeg 7.1.5.
- **Suite in the container:** 1684 passed, 11 skipped, in 42 seconds, on the first attempt.
- **Suite natively on Windows** (Python 3.13.15), for comparison: 1685 passed, 10 skipped.
- **Skipped in the container:** six optional engines and packages not installed (Coqui, Piper, liblouis, spaCy, pygrabber, OpenCV), four WordNet tests (the corpus is not downloaded), and one test that always skips.

## See also

- [Architecture & Contributing](architecture.md): the package layout and how to run the tests natively.
- [Documentation index](README.md)
