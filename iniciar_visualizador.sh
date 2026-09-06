#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

PYTHON_EXEC="python3"
if [ -n "$HOME" ] && [ -f "$HOME/miniconda3/envs/pdf-classifier/bin/python" ]; then
    PYTHON_EXEC="$HOME/miniconda3/envs/pdf-classifier/bin/python"
elif [ -n "$CONDA_PREFIX" ] && [ -f "$CONDA_PREFIX/bin/python" ]; then
    PYTHON_EXEC="$CONDA_PREFIX/bin/python"
elif [ -f "$DIR/.venv/bin/python" ]; then
    PYTHON_EXEC="$DIR/.venv/bin/python"
fi

exec "$PYTHON_EXEC" "$DIR/servidor_visualizador.py" "$@"
