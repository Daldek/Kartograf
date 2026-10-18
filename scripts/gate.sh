#!/usr/bin/env bash
# Jedna komenda bramy Kartografa (STANDARDS 6.3, 8.3, 18): ruff check, ruff format
# --check, mypy i pytest offline; pierwszy kod != 0 konczy skrypt tym kodem.
# Argumenty trafiaja do pytest, np.: scripts/gate.sh -x -k parity
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

find_python() {
  if [[ -n "${KARTOGRAF_PYTHON:-}" ]]; then
    printf '%s\n' "$KARTOGRAF_PYTHON"
    return
  fi
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    printf '%s\n' "$ROOT/.venv/bin/python"
    return
  fi
  # worktree bez wlasnego .venv: srodowisko glownego checkoutu
  local common main
  if common="$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"; then
    main="$(dirname "$common")"
    if [[ -x "$main/.venv/bin/python" ]]; then
      printf '%s\n' "$main/.venv/bin/python"
      return
    fi
  fi
  return 1
}

if ! PY="$(find_python)"; then
  echo "gate: brak Pythona - ustaw KARTOGRAF_PYTHON albo utworz .venv (STANDARDS 6.1)" >&2
  exit 2
fi

# Kontrola 0: kod testowany to kod tego checkoutu (instalacja edytowalna wskazuje
# glowny checkout, a worktree ma sprawdzac wlasne zrodla - dlatego kazdy krok idzie
# przez "$PY" -m ... z cwd = korzen).
package="$("$PY" -c 'import kartograf; print(kartograf.__file__)')"
case "$package" in
  "$ROOT"/*) ;;
  *)
    echo "gate: brama sprawdza inny checkout ($package), a nie $ROOT" >&2
    exit 2
    ;;
esac

started=$SECONDS
echo "== ruff check"
"$PY" -m ruff check .
echo "== ruff format --check"
"$PY" -m ruff format --check .
echo "== mypy"
"$PY" -m mypy kartograf/ tests/
echo "== pytest (offline)"
"$PY" -m pytest tests/ -m "not live" -q "$@"
echo "GATE OK ($((SECONDS - started)) s)"
