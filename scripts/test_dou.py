"""Teste isolado do DOUIngestor — sem classificação (custo zero)."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import structlog

from src.ingestion.dou import DOUIngestor

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)


async def main() -> None:
    print("=" * 70, flush=True)
    print("TESTE DO DOU INGESTOR", flush=True)
    print("=" * 70, flush=True)

    ingestor = DOUIngestor(
        max_per_query=20,
        filter_industrial=True,
        fetch_full_text=False,
    )

    print(f"\nFonte: {ingestor.source_name}", flush=True)
    print(f"Queries: {len(ingestor._queries)}", flush=True)
    print(f"Blacklist: {len(ingestor._blacklist)} termos\n", flush=True)

    records = await ingestor.fetch()

    print(f"\n{'=' * 70}", flush=True)
    print(f"RESULTADO: {len(records)} registros coletados", flush=True)
    print(f"{'=' * 70}", flush=True)

    if records:
        # Salvar em arquivo para inspeção
        out_path = Path("data/raw/dou_sample.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        print(f"\nAmostra gravada em: {out_path}", flush=True)

        print("\n--- Primeiros 3 registros ---", flush=True)
        for i, r in enumerate(records[:3], 1):
            print(f"\n[{i}] {r.get('tipo_ato', 'N/A')} | {r.get('data_reclamacao', 'N/A')}")
            print(f"    Órgão: {(r.get('orgao') or '')[:80]}")
            print(f"    Empresa: {r.get('nome_empresa') or 'N/D'}")
            print(f"    Produto: {r.get('nome_produto') or 'N/D'}")
            print(f"    Sev. inferida: {r.get('severidade_inferida')}")
            print(f"    URL: {r.get('materia_url')}")
            texto = r.get("texto_reclamacao", "")
            print(f"    Texto ({len(texto)} chars): {texto[:200]}...")


if __name__ == "__main__":
    asyncio.run(main())
