"""Teste direto do NotivisaIngestor."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import structlog

from src.ingestion.notivisa import NotivisaIngestor

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
    print("TESTE DO NOTIVISA INGESTOR", flush=True)
    print("=" * 70, flush=True)

    ingestor = NotivisaIngestor(
        include_registros=True,
        include_manual=True,
        filter_industrial=True,
    )

    print(f"\nFonte: {ingestor.source_name}", flush=True)
    print(f"Dir manual: {ingestor._notivisa_dir}", flush=True)
    print(f"Blacklist carregada: {len(ingestor._blacklist)} termos\n", flush=True)

    records = await ingestor.fetch()

    print(f"\n{'=' * 70}", flush=True)
    print(f"RESULTADO: {len(records)} registros coletados", flush=True)
    print(f"{'=' * 70}", flush=True)

    if records:
        print("\nPrimeiros 3 registros:", flush=True)
        for i, r in enumerate(records[:3], 1):
            print(f"\n--- Registro {i} ---", flush=True)
            print(f"  ID: {r.get('id', 'N/A')}", flush=True)
            print(f"  Tipo: {r.get('tipo_dado', 'N/A')}", flush=True)
            print(f"  Empresa: {r.get('nome_empresa', 'N/A')}", flush=True)
            print(f"  Produto: {r.get('nome_produto', 'N/A')}", flush=True)
            texto = r.get("texto_reclamacao", "")
            print(f"  Texto: {texto[:200]}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
