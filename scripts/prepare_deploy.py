"""Gera subset do classificados.json para deploy público.

Aplica o mesmo filtro industrial que o dashboard usa em runtime e salva
em `data/classified/classificados_deploy.json`. Este arquivo fica ~200 KB
(vs. 36 MB do original) e é seguro para commit no GitHub público/privado.

Uso:
    python scripts/prepare_deploy.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from src.dashboard.components.data_loader import _is_industrial  # noqa: E402

SRC = _ROOT / "data" / "classified" / "classificados.json"
DST = _ROOT / "data" / "classified" / "classificados_deploy.json"


def main() -> None:
    if not SRC.exists():
        print(f"ERRO: {SRC} não existe. Rode o pipeline primeiro.")
        sys.exit(1)

    with open(SRC, encoding="utf-8") as f:
        raw = json.load(f)

    kept = []
    for rec in raw:
        fonte = rec.get("fonte", "")
        empresa = rec.get("empresa", "") or ""
        # DOU sempre passa; Consumidor.gov passa se empresa não for industrial
        if fonte == "dou_anvisa" or not _is_industrial(empresa):
            kept.append(rec)

    DST.parent.mkdir(parents=True, exist_ok=True)
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)

    src_mb = SRC.stat().st_size / 1024 / 1024
    dst_kb = DST.stat().st_size / 1024

    print(f"Original: {SRC.name} — {len(raw):,} registros ({src_mb:.1f} MB)")
    print(f"Deploy:   {DST.name} — {len(kept):,} registros ({dst_kb:.0f} KB)")
    print(f"Redução: {(1 - DST.stat().st_size / SRC.stat().st_size) * 100:.1f}%")


if __name__ == "__main__":
    main()
