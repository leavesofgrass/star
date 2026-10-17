# star development and Linux test image.  See docs/docker.md.
#
# Debian trixie with its Python 3.13, the speech engines star drives on Linux
# (espeak-ng, speech-dispatcher), pandoc, ffmpeg, and the runtime libraries
# PyQt6's offscreen platform needs (the ones CI installs, plus the fonts,
# fontconfig and GLib a GitHub runner already has).  The image holds star's
# Python dependencies and an editable install of star pointing at /work; the
# checkout is mounted at /work at run time, so the code under test is always
# the mounted worktree's.
#
# Build:  docker compose build dev
# Use:    docker compose run --rm -T dev bash tools/ci-pytest.sh python -m pytest
#
# The build context is the repository root, filtered to three files by
# docker/Dockerfile.dockerignore.

# ── The dependency list, from pyproject.toml ─────────────────────────────────
# star's own dependencies plus the `all` and `test` extras.  Only a change to
# this list re-runs the slow install below.
FROM debian:trixie-slim AS requirements
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 \
 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml /src/pyproject.toml
RUN python3 - <<'EOF'
import tomllib

project = tomllib.load(open("/src/pyproject.toml", "rb"))["project"]
extras = project["optional-dependencies"]
lines = []
for spec in [*project["dependencies"], *extras["all"], *extras["test"]]:
    if spec not in lines:
        lines.append(spec)
open("/requirements.txt", "w").write("\n".join(lines) + "\n")
EOF

# ── The development image ────────────────────────────────────────────────────
FROM debian:trixie-slim
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      python3 python3-venv \
      espeak-ng espeak-ng-data \
      speech-dispatcher \
      pandoc \
      ffmpeg \
      libegl1 libgl1 libxkbcommon0 libdbus-1-3 libxcb-cursor0 \
      libglib2.0-0t64 libfontconfig1 libfreetype6 fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

# Debian's Python is externally managed (PEP 668), so star's packages go in a
# virtual environment.
ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    LANG=C.UTF-8 \
    PYTHONUTF8=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
RUN python3 -m venv /opt/venv
COPY --from=requirements /requirements.txt /opt/requirements.txt
RUN pip install -r /opt/requirements.txt

# An editable install registers star's entry points (backends, formats,
# exporters), which star's plugin registry reads.  It is made against a stub
# package at /work, the path the checkout is mounted at, so at run time the
# install resolves to the mounted worktree's star/.  Rebuild the image after
# pyproject.toml changes (new entry points, new dependencies).
COPY pyproject.toml README.md LICENSE /work/
RUN mkdir -p /work/star \
 && printf '"""Stub replaced by the mounted checkout at run time."""\n' > /work/star/__init__.py \
 && pip install --no-deps -e /work

# /target is each agent's own named volume (compose.yaml).  A new volume is
# filled from the image's /target, so these folders exist in every one.
RUN mkdir -p /target/tmp /target/pycache /target/hypothesis

WORKDIR /work
CMD ["bash"]
