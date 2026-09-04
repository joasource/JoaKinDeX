#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

PYTHON_EXEC="python3"
if [ -n "$CONDA_PREFIX" ] && [ -f "$CONDA_PREFIX/bin/python" ]; then
    PYTHON_EXEC="$CONDA_PREFIX/bin/python"
elif [ -f "$DIR/.venv/bin/python" ]; then
    PYTHON_EXEC="$DIR/.venv/bin/python"
fi

echo "[*] Iniciando servidor do Visualizador..."
echo "[*] Pressione Ctrl+C a qualquer momento para parar."

"$PYTHON_EXEC" "$DIR/servidor_visualizador.py" "$@"
