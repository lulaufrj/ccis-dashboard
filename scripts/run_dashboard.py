"""Inicia o dashboard Streamlit.

Atalho equivalente a:
    streamlit run src/dashboard/app.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    app_path = root / "src" / "dashboard" / "app.py"

    if not app_path.exists():
        print(f"[ERRO] Dashboard não encontrado em {app_path}", file=sys.stderr)
        return 1

    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path)]
    print(f"Iniciando dashboard: {' '.join(cmd)}")
    print(f"Dashboard abrirá em http://localhost:8501\n")

    return subprocess.call(cmd, cwd=str(root))


if __name__ == "__main__":
    sys.exit(main())
