#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  install-star.sh  —  One-command installer for star
#  Speaking Terminal Access Reader  ·  https://github.com/leavesofgrass/star
#
#  Clones the repo, installs all system and Python dependencies,
#  creates a venv, and adds a 'star' launcher to your PATH.
#
#  Supported platforms
#    macOS    Homebrew (installed automatically if absent)
#    Linux    Debian/Ubuntu · Arch/CachyOS/Manjaro · Fedora/RHEL
#             openSUSE · Alpine — auto-detected
#    Windows  Git Bash / MSYS2 — via Scoop, winget, or Chocolatey
#             (WSL users: just run as Linux)
#
#  Usage
#    bash install-star.sh          # interactive
#    bash install-star.sh -y       # non-interactive (accept all defaults)
#    curl -fsSL <raw-url> | bash   # run straight from the web
#
#  Environment overrides
#    STAR_DIR   where to clone star  (default: ~/star)
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail
IFS=$'\n\t'

# ── Colour helpers ────────────────────────────────────────────────────────
R='\033[0;31m' G='\033[0;32m' Y='\033[1;33m' B='\033[0;34m' W='\033[1m' N='\033[0m'
nfo()  { printf "${B}  →${N}  %s\n"    "$*"; }
ok()   { printf "${G}  ✔${N}  %s\n"    "$*"; }
warn() { printf "${Y}  ⚠${N}  %s\n"    "$*"; }
die()  { printf "${R}  ✘${N}  %s\n" "$*" >&2; exit 1; }
hdr()  { printf "\n${W}${B}━━  %s  ━━${N}\n" "$*"; }

# ── Config ────────────────────────────────────────────────────────────────
STAR_DIR="${STAR_DIR:-$HOME/star}"
STAR_REPO="https://github.com/leavesofgrass/star.git"

# -y / --yes  →  non-interactive (also auto-enabled when stdin is a pipe)
YES=false
for _arg in "${@:-}"; do
    [[ "$_arg" == "-y" || "$_arg" == "--yes" ]] && YES=true
done
[[ -t 0 ]] || YES=true   # curl | bash → no tty → go non-interactive

confirm() {
    $YES && return 0
    local _ans
    read -r -p "  $1 [Y/n] " _ans
    [[ "${_ans:-y}" =~ ^[Yy]$ ]]
}

has() { command -v "$1" &>/dev/null; }

# ── Detect OS / arch ──────────────────────────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"

# True when running inside any Windows bash environment (Git Bash, MSYS2, Cygwin).
# WSL reports Linux and follows the Linux path — intentionally not caught here.
is_windows() { [[ "$OS" == MINGW* || "$OS" == MSYS* || "$OS" == CYGWIN* ]]; }

# Convert a Unix-style shell path to a Windows-native path (for PowerShell).
# cygpath is available in both Git Bash and MSYS2; falls back to regex + Python.
win_path() {
    if has cygpath; then
        cygpath -w "$1"
    elif [[ -n "${PYTHON:-}" ]]; then
        "$PYTHON" -c "import os, sys; print(os.path.normpath(sys.argv[1]))" "$1"
    else
        # Manual heuristic: /c/Users/... → C:\Users\...
        local p="$1"
        if [[ "$p" =~ ^/([a-zA-Z])/(.*) ]]; then
            echo "${BASH_REMATCH[1]}:\\${BASH_REMATCH[2]//\//\\}"
        else
            echo "$p"
        fi
    fi
}

# ═════════════════════════════════════════════════════════════════════════
#  macOS
# ═════════════════════════════════════════════════════════════════════════
install_macos() {
    hdr "macOS setup"

    # ── Homebrew ──────────────────────────────────────────────────────────
    if ! has brew; then
        nfo "Homebrew not found — installing…"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi

    # Ensure brew is on PATH (Apple Silicon: /opt/homebrew, Intel: /usr/local)
    if [[ "$ARCH" == "arm64" && -x /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -x /usr/local/bin/brew ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
    ok "Homebrew $(brew --version | head -1)"

    # ── System packages via Homebrew ──────────────────────────────────────
    # brew install is a no-op when a package is already current.
    local brew_pkgs=(espeak-ng tesseract pandoc ffmpeg liblouis)
    has git     || brew_pkgs+=(git)
    has python3 || brew_pkgs+=(python)

    nfo "Installing system tools via Homebrew: ${brew_pkgs[*]}"
    brew install "${brew_pkgs[@]}" 2>/dev/null || true
    ok "System tools ready"

    # Prefer brew's python3 over the Xcode command-line stub
    PYTHON="$(brew --prefix)/bin/python3"
    [[ -x "$PYTHON" ]] || PYTHON="python3"
}

# ═════════════════════════════════════════════════════════════════════════
#  Linux — distro detection + per-distro package installation
# ═════════════════════════════════════════════════════════════════════════
detect_linux_distro() {
    DISTRO="unknown"
    DISTRO_LIKE=""
    if [[ -f /etc/os-release ]]; then
        # shellcheck source=/dev/null
        source /etc/os-release
        DISTRO="${ID:-unknown}"
        DISTRO_LIKE="${ID_LIKE:-}"
    elif has lsb_release; then
        DISTRO="$(lsb_release -si | tr '[:upper:]' '[:lower:]')"
    fi
}

install_linux() {
    hdr "Linux setup"
    detect_linux_distro
    nfo "Distro: $DISTRO  (like: ${DISTRO_LIKE:-—})"

    # ── Pick package manager ───────────────────────────────────────────────
    # Priority: AUR helpers (paru > yay) for Arch family, then distro tools.
    local pm="" install_cmd=()

    if has paru; then
        pm="paru";    install_cmd=(paru -S --noconfirm --needed)
    elif has yay; then
        pm="yay";     install_cmd=(yay -S --noconfirm --needed)
    elif has pacman; then
        pm="pacman";  install_cmd=(sudo pacman -S --noconfirm --needed)
    elif has apt-get; then
        pm="apt";     install_cmd=(sudo apt-get install -y)
        nfo "Updating apt package index…"
        sudo apt-get update -qq
    elif has dnf; then
        pm="dnf";     install_cmd=(sudo dnf install -y)
    elif has zypper; then
        pm="zypper";  install_cmd=(sudo zypper install -y --no-recommends)
    elif has apk; then
        pm="apk";     install_cmd=(sudo apk add --no-cache)
    else
        warn "No recognised package manager found."
        warn "Please install manually: git python3 pip espeak-ng tesseract pandoc ffmpeg liblouis"
        pm="unknown"
    fi

    nfo "Package manager: $pm"

    # ── Per-distro package lists ───────────────────────────────────────────
    local pkgs=()
    case "$pm" in
      paru|yay|pacman)
        # Arch / CachyOS / Manjaro
        # pandoc-cli is the current split package on Arch (replaces pandoc)
        pkgs=(
            git python python-pip
            espeak-ng
            tesseract tesseract-data-eng
            pandoc-cli
            ffmpeg
            liblouis
        )
        ;;
      apt)
        # Debian / Ubuntu / Mint / Pop!_OS / Raspberry Pi OS / …
        pkgs=(
            git python3 python3-pip python3-venv
            espeak-ng
            tesseract-ocr tesseract-ocr-eng
            pandoc
            ffmpeg
            liblouis-dev
        )
        ;;
      dnf)
        # Fedora / RHEL / CentOS Stream / Rocky / Alma
        pkgs=(
            git python3 python3-pip
            espeak-ng
            tesseract tesseract-langpack-eng
            pandoc
            ffmpeg
            liblouis
        )
        ;;
      zypper)
        # openSUSE Leap / Tumbleweed
        pkgs=(
            git python3 python3-pip
            espeak-ng
            tesseract-ocr
            pandoc
            ffmpeg
            liblouis0
        )
        ;;
      apk)
        # Alpine Linux
        pkgs=(
            git python3 py3-pip
            espeak-ng
            tesseract-ocr tesseract-ocr-data-eng
            pandoc
            ffmpeg
        )
        ;;
    esac

    if [[ ${#pkgs[@]} -gt 0 ]]; then
        nfo "Installing: ${pkgs[*]}"
        "${install_cmd[@]}" "${pkgs[@]}" \
            || warn "Some packages may have failed — continuing anyway"
        ok "System packages installed"
    fi

    # Resolve python3 binary (might be 'python' on Arch)
    if has python3; then
        PYTHON="python3"
    elif has python; then
        PYTHON="python"
    else
        die "python3 not found after package install. Check the output above."
    fi
}

# ═════════════════════════════════════════════════════════════════════════
#  Windows — Git Bash / MSYS2 / Cygwin
# ═════════════════════════════════════════════════════════════════════════
install_windows() {
    hdr "Windows setup  ($OS)"

    # ── Pick Windows package manager ──────────────────────────────────────
    # Scoop is preferred: user-space, no admin rights needed.
    local pm="none"
    if has scoop; then
        pm="scoop"
    elif has winget; then
        pm="winget"
    elif has choco; then
        pm="choco"
    fi
    nfo "Package manager: $pm"

    case "$pm" in
      scoop)
        # Add the 'extras' bucket — home of tesseract and espeak-ng
        nfo "Ensuring Scoop 'extras' bucket…"
        scoop bucket add extras 2>/dev/null || true

        nfo "Installing system tools via Scoop…"
        scoop install git python pandoc ffmpeg tesseract \
            || warn "Some Scoop packages may have failed"

        # eSpeak-NG is optional — pyttsx3 uses SAPI5 natively on Windows
        scoop install espeak-ng 2>/dev/null \
            || scoop install espeak 2>/dev/null \
            || warn "eSpeak-NG not installed (pyttsx3 uses SAPI5 by default — this is fine)"
        ;;

      winget)
        nfo "Installing system tools via winget…"
        local winget_flags=(
            --silent
            --accept-source-agreements
            --accept-package-agreements
        )
        # winget installs one package per invocation; || true so one failure doesn't stop the rest
        local wids=(
            "Git.Git"
            "Python.Python.3"
            "JohnMacFarlane.Pandoc"
            "Gyan.FFmpeg"
            "UB-Mannheim.TesseractOCR"
        )
        for wid in "${wids[@]}"; do
            nfo "  winget → $wid"
            winget install "${winget_flags[@]}" --id "$wid" \
                || warn "  Could not install $wid (may already be present or ID changed)"
        done
        # Optional eSpeak-NG backend
        winget install "${winget_flags[@]}" --id "eSpeak.eSpeakNG" 2>/dev/null \
            || warn "eSpeak-NG not installed (pyttsx3 uses SAPI5 by default — this is fine)"
        warn "Newly installed tools may not appear until you restart your terminal."
        ;;

      choco)
        nfo "Installing system tools via Chocolatey…"
        choco install -y git python pandoc ffmpeg tesseract espeak-ng \
            || warn "Some Chocolatey packages may have failed"
        warn "Newly installed tools may not appear until you restart your terminal."
        ;;

      none)
        warn "No Windows package manager found (Scoop / winget / Chocolatey)."
        warn "For the easiest setup, install Scoop first:  https://scoop.sh"
        warn "Continuing — only tools already on PATH will be available."
        ;;
    esac

    ok "System tools step complete"

    # ── Resolve Python ────────────────────────────────────────────────────
    PYTHON=""
    if has python3 && python3 -c 'import sys; sys.exit(0 if sys.version_info[0]==3 else 1)' 2>/dev/null; then
        PYTHON="python3"
    elif has python && python -c 'import sys; sys.exit(0 if sys.version_info[0]==3 else 1)' 2>/dev/null; then
        PYTHON="python"
    elif has py; then
        # Python Launcher for Windows — ask it for the actual interpreter path
        local _pyexe
        _pyexe="$(py -3 -c 'import sys; print(sys.executable)' 2>/dev/null)" \
            && PYTHON="$_pyexe" \
            || true
    fi

    [[ -n "$PYTHON" ]] \
        || die "Python 3 not found. Install from https://python.org or run: winget install Python.Python.3"

    ok "Python: $PYTHON"
}

# ═════════════════════════════════════════════════════════════════════════
#  Clone / update repository
# ═════════════════════════════════════════════════════════════════════════
clone_star() {
    hdr "Repository"
    if [[ -d "$STAR_DIR/.git" ]]; then
        nfo "Repository found at $STAR_DIR — pulling latest…"
        git -C "$STAR_DIR" pull --ff-only \
            || warn "Could not pull latest; using existing copy"
    else
        nfo "Cloning into $STAR_DIR…"
        git clone "$STAR_REPO" "$STAR_DIR"
    fi
    ok "Source ready at $STAR_DIR"
}

# ═════════════════════════════════════════════════════════════════════════
#  Python virtualenv + packages
# ═════════════════════════════════════════════════════════════════════════
setup_python() {
    hdr "Python environment"

    # Verify Python 3.8+
    local pyver
    pyver="$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    local major minor
    major="${pyver%%.*}"
    minor="${pyver##*.}"
    if [[ "$major" -lt 3 || ( "$major" -eq 3 && "$minor" -lt 8 ) ]]; then
        die "Python $pyver found — star requires Python 3.8 or newer."
    fi
    ok "Python $pyver"

    # Create virtualenv inside the cloned repo directory
    local venv="$STAR_DIR/.venv"
    if [[ ! -d "$venv" ]]; then
        nfo "Creating virtualenv at $venv…"
        "$PYTHON" -m venv "$venv"
    else
        nfo "Virtualenv already exists at $venv"
    fi

    # Windows venv uses Scripts/; Unix uses bin/
    local venv_scripts
    if is_windows; then
        venv_scripts="$venv/Scripts"
    else
        venv_scripts="$venv/bin"
    fi
    local pip="$venv_scripts/pip"

    nfo "Upgrading pip…"
    "$pip" install --quiet --upgrade pip

    # ── Core optional packages (cross-platform) ───────────────────────────
    nfo "Installing Python packages (this may take a minute)…"
    "$pip" install --quiet \
        PyQt6          \
        pyttsx3        \
        "pdfminer.six" \
        pytesseract    \
        pymupdf        \
        python-docx    \
        python-pptx    \
        odfpy          \
        openpyxl       \
        pypandoc       \
        pydub

    # ── windows-curses — required for TUI mode on Windows ─────────────────
    if is_windows; then
        nfo "Installing windows-curses (TUI support)…"
        "$pip" install --quiet windows-curses \
            || warn "windows-curses failed — TUI mode (--tui) may not work in this terminal"
    fi

    # ── louis (braille BRF export) — needs system liblouis ────────────────
    # On Windows, liblouis.dll is not readily available; skip and warn.
    # On Linux/macOS it should succeed if liblouis was installed above.
    if is_windows; then
        warn "Skipping 'louis' on Windows — braille BRF export requires manual liblouis setup"
    else
        "$pip" install --quiet louis \
            || warn "louis not installed — braille BRF export unavailable (ensure liblouis is installed)"
    fi

    ok "Python packages installed"
}

# ═════════════════════════════════════════════════════════════════════════
#  Launcher scripts
# ═════════════════════════════════════════════════════════════════════════
create_launcher() {
    hdr "Launcher"
    local launcher="$STAR_DIR/star"

    if is_windows; then
        # Bash launcher (Git Bash / MSYS2) — venv uses Scripts/ on Windows
        cat > "$launcher" <<'LAUNCHER_SCRIPT'
#!/usr/bin/env bash
# star — bash launcher (Git Bash / MSYS2) generated by install-star.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/.venv/Scripts/python" "$SCRIPT_DIR/star.py" "$@"
LAUNCHER_SCRIPT

        # .bat launcher (Command Prompt)
        printf '@echo off\r\n"%dp0.venv\\Scripts\\python.exe" "%dp0star.py" %%*\r\n' \
            > "$STAR_DIR/star.bat"
        ok "Launcher (cmd):        $STAR_DIR/star.bat"

        # .ps1 launcher (PowerShell)
        printf -- '$d=Split-Path -Parent $MyInvocation.MyCommand.Path\r\n& "$d\.venv\Scripts\python.exe" "$d\star.py" @args\r\n' \
            > "$STAR_DIR/star.ps1"
        ok "Launcher (PowerShell): $STAR_DIR/star.ps1"

    else
        cat > "$launcher" <<'LAUNCHER_SCRIPT'
#!/usr/bin/env bash
# star — launcher generated by install-star.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/star.py" "$@"
LAUNCHER_SCRIPT
    fi

    chmod +x "$launcher"
    ok "Launcher (bash):      $launcher"
}

# ═════════════════════════════════════════════════════════════════════════
#  PATH integration
# ═════════════════════════════════════════════════════════════════════════
install_to_path() {
    hdr "PATH integration"

    if is_windows; then
        _path_windows
    else
        _path_unix
    fi
}

_path_unix() {
    local local_bin="$HOME/.local/bin"
    mkdir -p "$local_bin"
    ln -sf "$STAR_DIR/star" "$local_bin/star"
    ok "Symlinked: $local_bin/star → $STAR_DIR/star"

    if echo ":${PATH}:" | grep -q ":${local_bin}:"; then
        ok "$local_bin is already on your PATH — 'star' is ready"
        return
    fi

    warn "$local_bin is not on your current PATH."

    local shell_rc=""
    if   [[ "$SHELL" == */zsh  ]]; then shell_rc="$HOME/.zshrc"
    elif [[ "$SHELL" == */bash ]]; then shell_rc="$HOME/.bashrc"
    elif [[ "$SHELL" == */fish ]]; then shell_rc="$HOME/.config/fish/config.fish"
    else                                shell_rc="$HOME/.profile"
    fi

    if confirm "Add ~/.local/bin to PATH in $shell_rc?"; then
        {
            echo ''
            echo '# Added by install-star.sh'
            if [[ "$shell_rc" == *.fish ]]; then
                echo 'fish_add_path ~/.local/bin'
            else
                echo 'export PATH="$HOME/.local/bin:$PATH"'
            fi
        } >> "$shell_rc"
        ok "PATH entry added to $shell_rc"
        warn "Restart your shell or run:  source $shell_rc"
    else
        nfo "Skipped — run star directly with: $STAR_DIR/star"
    fi
}

_path_windows() {
    local win_dir
    win_dir="$(win_path "$STAR_DIR")"
    nfo "Star directory (Windows path): $win_dir"

    if confirm "Add $win_dir to your Windows user PATH?"; then
        # Write a small PowerShell script to avoid escaping nightmares in -Command
        local tmpps="/tmp/star-addpath-$$.ps1"
        {
            printf '$d = "%s"\n' "$win_dir"
            printf '$p = [Environment]::GetEnvironmentVariable("PATH","User")\n'
            printf 'if ($p -notlike "*$d*") {\n'
            printf '    [Environment]::SetEnvironmentVariable("PATH","$p;$d","User")\n'
            printf '    "PATH updated."\n'
            printf '} else { "Already in PATH." }\n'
        } > "$tmpps"

        local tmpps_win
        tmpps_win="$(win_path "$tmpps")"

        powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$tmpps_win" \
            && ok "Windows user PATH updated — restart your terminal to use 'star'" \
            || warn "Could not update PATH automatically. Add this to your PATH manually: $win_dir"

        rm -f "$tmpps"
    else
        nfo "You can run star with:"
        nfo "  Git Bash:          $STAR_DIR/star"
        nfo "  Command Prompt:    $win_dir\\star.bat"
        nfo "  PowerShell:        $win_dir\\star.ps1"
    fi
}

# ═════════════════════════════════════════════════════════════════════════
#  Success banner
# ═════════════════════════════════════════════════════════════════════════
print_done() {
    printf "\n${G}${W}═══════════════════════════════════════════════${N}\n"
    printf "${G}${W}  star installed successfully!${N}\n"
    printf "${G}${W}═══════════════════════════════════════════════${N}\n\n"
    printf "  ${W}Open a document:${N}\n"
    printf "    star document.pdf\n"
    printf "    star https://example.com\n"
    printf "    star --tui report.docx       # force terminal UI\n\n"

    if is_windows; then
        local win_dir
        win_dir="$(win_path "$STAR_DIR")"
        printf "  ${W}Windows launchers (all do the same thing):${N}\n"
        printf "    %s\\star.bat    (Command Prompt)\n" "$win_dir"
        printf "    %s\\star.ps1   (PowerShell)\n" "$win_dir"
        printf "    %s/star         (Git Bash)\n\n" "$STAR_DIR"
        printf "  ${W}If 'star' is not found yet:${N}\n"
        printf "    Restart your terminal — or add this to PATH:\n"
        printf "    %s\n\n" "$win_dir"
    else
        printf "  ${W}If 'star' is not found yet:${N}\n"
        printf "    source ~/.bashrc             # (or ~/.zshrc)\n"
        printf "    # — or run directly:\n"
        printf "    %s/star document.pdf\n\n" "$STAR_DIR"
    fi

    printf "  ${W}Installed to:${N}  ${B}%s${N}\n\n" "$STAR_DIR"
}

# ═════════════════════════════════════════════════════════════════════════
#  Entry point
# ═════════════════════════════════════════════════════════════════════════
hdr "star installer"
nfo "Install directory : $STAR_DIR"
nfo "Platform          : $OS / $ARCH"

case "$OS" in
    Darwin)               install_macos   ;;
    Linux)                install_linux   ;;
    MINGW*|MSYS*|CYGWIN*) install_windows ;;
    *) die "Unsupported OS: $OS  (Linux, macOS, and Windows via Git Bash/MSYS2 are supported)" ;;
esac

clone_star
setup_python
create_launcher
install_to_path
print_done
