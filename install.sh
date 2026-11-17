#!/usr/bin/env bash
# install.sh - installs the dependencies (ffmpeg, pipx) and then remuxy (the `remux` and `remuxy` commands).
#
#   curl -fsSL https://raw.githubusercontent.com/JeanPoffo/remuxy/main/install.sh | bash
#                             installs (or updates) remuxy from GitHub, no clone needed
#   ... | bash -s -- --uninstall
#                             removes remuxy (keeps ffmpeg and pipx)
#   ./install.sh [--dev]      from a clone: installs that folder (--dev = editable, code changes apply at once)
#
# Detects the package manager: apt (Debian, Ubuntu, Mint, Pop!_OS...) or pacman (Arch, Manjaro,
# EndeavourOS...). Run it as a regular user: sudo is only requested to install the system packages.
set -euo pipefail

# ------------------------------------------------------------------ colored output (remuxy palette)
if [[ -t 1 ]]; then
    LILAC=$'\e[38;2;195;166;255m'; ORANGE=$'\e[38;2;224;136;79m'; RED=$'\e[38;2;232;109;109m'
    GREEN=$'\e[38;2;143;209;158m'; DIM=$'\e[38;2;109;112;146m'; BOLD=$'\e[1m'; RESET=$'\e[0m'
else
    LILAC=""; ORANGE=""; RED=""; GREEN=""; DIM=""; BOLD=""; RESET=""
fi
step() { printf '\n%s%s==> %s%s\n' "$BOLD" "$LILAC" "$*" "$RESET"; }
info() { printf '    %s\n' "$*"; }
ok()   { printf '    %s✓%s %s\n' "$GREEN" "$RESET" "$*"; }
warn() { printf '    %s! %s%s\n' "$ORANGE" "$*" "$RESET"; }
die()  { printf '\n%s✗ %s%s\n' "$RED" "$*" "$RESET" >&2; exit 1; }

usage() {
    cat <<'TXT'
remuxy installer

  curl -fsSL https://raw.githubusercontent.com/JeanPoffo/remuxy/main/install.sh | bash
                            installs (or updates) remuxy from GitHub
  ... | bash -s -- --uninstall
                            removes remuxy (keeps ffmpeg and pipx)
  ./install.sh [--dev]      from a clone; --dev = editable install
TXT
}

# ------------------------------------------------------------------ options
MODE=install
for arg in "$@"; do
    case "$arg" in
        --dev) MODE=dev ;;
        --uninstall) MODE=uninstall ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $arg (use --help)" ;;
    esac
done

# What pipx installs: the clone this script sits in, or (when piped from curl) the GitHub main branch.
# REMUXY_SOURCE overrides it (any pip-installable path or URL).
HERE=""
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
    HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    [[ -f "$HERE/pyproject.toml" ]] || HERE=""
fi
SOURCE="${REMUXY_SOURCE:-${HERE:-https://github.com/JeanPoffo/remuxy/archive/refs/heads/main.zip}}"
if [[ $MODE == dev && -z "$HERE" ]]; then
    die "--dev needs a clone: git clone https://github.com/JeanPoffo/remuxy.git && cd remuxy && ./install.sh --dev"
fi

printf '%s↪remuxy%s %sinstaller%s\n' "$ORANGE" "$RESET" "$DIM" "$RESET"

# running everything with sudo would install remuxy into root's account, and the command would not show up for the user
if [[ $EUID -eq 0 && -n "${SUDO_USER:-}" ]]; then
    die "do not run with sudo. Run ./install.sh as your user; sudo is only requested for the system packages."
fi

# ------------------------------------------------------------------ uninstall
if [[ $MODE == uninstall ]]; then
    step "Removing remuxy"
    if command -v pipx >/dev/null 2>&1 && pipx list --short 2>/dev/null | grep -q '^remuxy '; then
        pipx uninstall remuxy
        ok "remuxy removed (ffmpeg and pipx stay installed)"
    else
        warn "remuxy is not installed through pipx; nothing to do"
    fi
    exit 0
fi

# ------------------------------------------------------------------ package manager
step "Detecting the system"
if command -v apt-get >/dev/null 2>&1; then
    PM=apt
elif command -v pacman >/dev/null 2>&1; then
    PM=pacman
else
    die "no supported package manager (apt or pacman). Install ffmpeg and pipx manually and run: pipx install \"$SOURCE\""
fi
# shellcheck disable=SC1091
DISTRO="$( (. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME:-}") || true)"
ok "${DISTRO:-Linux} · package manager: $PM"

SUDO=()
if [[ $EUID -ne 0 ]]; then
    command -v sudo >/dev/null 2>&1 || die "sudo is not available; run as root or install sudo."
    SUDO=(sudo)
fi

# system package for each command, per package manager
pkg_for() {
    case "$PM:$1" in
        apt:ffmpeg|apt:ffprobe) echo ffmpeg ;;
        apt:pipx)               echo pipx ;;
        apt:python3)            echo python3 ;;
        pacman:ffmpeg|pacman:ffprobe) echo ffmpeg ;;
        pacman:pipx)            echo python-pipx ;;
        pacman:python3)         echo python ;;
    esac
}

pm_install() {
    case "$PM" in
        apt)
            info "${DIM}sudo apt-get install $*${RESET}"
            "${SUDO[@]}" apt-get update -qq
            "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$@"
            ;;
        pacman)
            info "${DIM}sudo pacman -S --needed $*${RESET}"
            "${SUDO[@]}" pacman -S --needed --noconfirm "$@"
            ;;
    esac
}

# ------------------------------------------------------------------ system dependencies
step "Checking the dependencies (python, ffmpeg, pipx)"
missing=()
for cmd in python3 ffmpeg ffprobe pipx; do
    if command -v "$cmd" >/dev/null 2>&1; then
        ok "$cmd already installed"
    else
        warn "$cmd not found"
        p="$(pkg_for "$cmd")"
        [[ " ${missing[*]-} " == *" $p "* ]] || missing+=("$p")
    fi
done
# on Debian/Ubuntu, pipx needs the venv module, which ships in a separate package
if [[ $PM == apt ]] && command -v python3 >/dev/null 2>&1 && ! python3 -c 'import ensurepip, venv' >/dev/null 2>&1; then
    warn "python3-venv not found (pipx needs it)"
    missing+=(python3-venv)
fi

if (( ${#missing[@]} )); then
    step "Installing: ${missing[*]}"
    if ! pm_install "${missing[@]}"; then
        # old distros (e.g. Ubuntu 20.04 without universe, Debian 10) have no pipx package
        if [[ " ${missing[*]} " == *" pipx "* ]] && ! command -v pipx >/dev/null 2>&1; then
            warn "the pipx package is not available; installing pipx with pip (for your user only)"
            others=()
            for p in "${missing[@]}"; do [[ $p == pipx ]] || others+=("$p"); done
            (( ${#others[@]} )) && pm_install "${others[@]}" python3-pip
            (( ${#others[@]} )) || pm_install python3-pip
            python3 -m pip install --user --upgrade pipx
            export PATH="$HOME/.local/bin:$PATH"
        else
            die "failed to install the system packages."
        fi
    fi
fi

command -v ffmpeg  >/dev/null 2>&1 || die "ffmpeg is still missing after the installation."
command -v ffprobe >/dev/null 2>&1 || die "ffprobe is still missing after the installation."
command -v pipx    >/dev/null 2>&1 || die "pipx is still missing after the installation."

python3 - <<'PY' || die "remuxy needs Python 3.9 or newer."
import sys
sys.exit(0 if sys.version_info >= (3, 9) else 1)
PY
ok "$(python3 --version) · $(ffmpeg -version | head -n1 | cut -d' ' -f1-3) · pipx $(pipx --version)"

# ------------------------------------------------------------------ remuxy
step "Installing remuxy with pipx"
if [[ $MODE == dev ]]; then
    info "editable mode: changes in $HERE/src take effect without reinstalling"
    pipx install --force --editable "$HERE"
else
    info "${DIM}pipx install $SOURCE${RESET}"
    pipx install --force "$SOURCE"
fi

# makes sure pipx's command folder (usually ~/.local/bin) is on PATH
BIN_DIR="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "$HOME/.local/bin")"
pipx ensurepath >/dev/null 2>&1 || true

step "Checking"
"$BIN_DIR/remux" --version >/dev/null && ok "remux  → $BIN_DIR/remux"
"$BIN_DIR/remuxy" --version >/dev/null && ok "remuxy → $BIN_DIR/remuxy"

printf '\n%s%sDone!%s\n' "$BOLD" "$GREEN" "$RESET"
info "${LILAC}remuxy${RESET}                          terminal UI"
info "${LILAC}remuxy dub.ac3 movie.mkv${RESET}        with source and target already filled in"
info "${LILAC}remux source target --auto-sync --verify${RESET}   command line"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) printf '\n'; warn "open a new terminal (or run: source ~/.bashrc) so the commands are on PATH" ;;
esac
