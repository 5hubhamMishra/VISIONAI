#!/usr/bin/env sh
set -eu

if [ -x ".venv312/Scripts/python.exe" ]; then
  PYTHON=".venv312/Scripts/python.exe"
elif [ -x ".venv312/bin/python" ]; then
  PYTHON=".venv312/bin/python"
elif [ -x ".venv/Scripts/python.exe" ]; then
  PYTHON=".venv/Scripts/python.exe"
elif [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="python"
fi

"$PYTHON" -m ruff check .
"$PYTHON" -m mypy src
"$PYTHON" -m pytest --cov=src/visionai --cov-report=term-missing

if [ "${SKIP_AUDIT:-0}" != "1" ]; then
  "$PYTHON" -m bandit -q -r src
  "$PYTHON" -m pip_audit -r requirements/base.txt -r requirements/dev.txt
fi
