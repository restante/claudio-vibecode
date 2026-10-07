#!/usr/bin/env bash
# claudio-vibecode installer for macOS (and Linux, best effort). Installs claudio-tts first if needed.
#
#   curl -fsSL https://raw.githubusercontent.com/restante/claudio-vibecode/main/install.sh | bash
#
# Options: --lite  --no-model  (passed to the claudio-tts installer)
#          --uninstall  --local  --dev  --ref <git ref>
set -euo pipefail

REPO="${CLAUDIO_VIBECODE_REPO:-restante/claudio-vibecode}"
TTS_REPO="${CLAUDIO_TTS_REPO:-restante/claudio-tts}"
REF="${CLAUDIO_VIBECODE_REF:-main}"
TTS_ARGS=() UNINSTALL=0 LOCAL=0 DEV=0

while [ $# -gt 0 ]; do
  case "$1" in
    --lite|--no-model) TTS_ARGS+=("$1") ;;
    --uninstall) UNINSTALL=1 ;;
    --local) LOCAL=1 ;;      # install from the checkout this script sits in
    --dev) DEV=1; LOCAL=1 ;; # like --local, editable, and link the mod instead of copying
    --ref) REF="$2"; shift ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

case "$(uname -s)" in
  Darwin) DEFAULT_HOME="$HOME/Library/Application Support/claudio-tts" ;;
  Linux)  DEFAULT_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/claudio-tts"
          warn "Linux is best effort: it should work, but it is not tested on real hardware." ;;
  *) die "Unsupported OS $(uname -s). On Windows use install.ps1." ;;
esac
HOME_DIR="${CLAUDIO_TTS_HOME:-$DEFAULT_HOME}"   # claudio-vibecode shares claudio-tts's environment
PY="$HOME_DIR/venv/bin/python"

if [ "$UNINSTALL" = 1 ]; then
  say "Uninstalling claudio-vibecode (claudio-tts is left alone)"
  if [ -x "$PY" ]; then
    "$PY" -m claudio_vibecode stop || true
    "$PY" -m claudio_vibecode uninstall-mod || true
    command -v uv >/dev/null && uv pip uninstall -q --python "$PY" claudio-vibecode || true
  fi
  rm -rf "$HOME_DIR/vibecode"
  say "Done. Restart open Claude Code sessions to drop the mod."
  exit 0
fi

command -v curl >/dev/null || die "curl is required."

# 1. claudio-tts (speech engine, Python environment, uv) --------------------------------------------
if [ ! -x "$PY" ] || ! "$PY" -c "import claudio_tts" 2>/dev/null; then
  say "Installing claudio-tts first (it provides the voice and the Python environment)"
  if [ "$LOCAL" = 1 ] && [ -f "$(dirname "${BASH_SOURCE[0]:-$0}")/../claudio-tts/install.sh" ]; then
    bash "$(dirname "${BASH_SOURCE[0]:-$0}")/../claudio-tts/install.sh" --local ${TTS_ARGS[@]+"${TTS_ARGS[@]}"}
  else
    curl -fsSL "https://raw.githubusercontent.com/$TTS_REPO/main/install.sh" | bash -s -- ${TTS_ARGS[@]+"${TTS_ARGS[@]}"}
  fi
fi
[ -x "$PY" ] || die "claudio-tts did not set up $PY"
command -v uv >/dev/null || export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
command -v uv >/dev/null || die "uv was not found; open a new terminal and re-run."

# 2. claudio-vibecode ----------------------------------------------------------------------------------
if [ "$LOCAL" = 1 ]; then
  SRC="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
  [ -f "$SRC/pyproject.toml" ] || die "--local needs to run from a claudio-vibecode checkout."
  say "Installing claudio-vibecode from $SRC"
  if [ "$DEV" = 1 ]; then uv pip install -q --python "$PY" --no-deps -e "$SRC"; else uv pip install -q --python "$PY" --no-deps "$SRC"; fi
  uv pip install -q --python "$PY" "segno>=1.6" "psutil>=5.9" "numpy>=1.26"
else
  say "Installing claudio-vibecode ($REPO@$REF)"
  uv pip install -q --python "$PY" "claudio-vibecode @ git+https://github.com/$REPO@$REF"
fi

# 3. Claude Code mod -------------------------------------------------------------------------------------
say "Installing the Claude Code mod"
if [ "$DEV" = 1 ]; then "$PY" -m claudio_vibecode install-mod --python "$PY" --link
else "$PY" -m claudio_vibecode install-mod --python "$PY"; fi

say "Checking everything"
"$PY" -m claudio_vibecode doctor || warn "Some checks failed; see above."

cat <<DONE

claudio-vibecode is installed.

  1. Restart Claude Code (open sessions only pick the mod up when they start).
  2. In a session type:  /vibe      It starts the hub and shows a QR code.
  3. Scan it with your phone camera (same Wi-Fi). Tap Listen to hear Claude's voice on the phone.

Other commands: /vibe status, /vibe devices, /vibe off, /vibe update
DONE
