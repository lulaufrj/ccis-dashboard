"""Script para coletar avaliações do Mercado Livre.

Uso:
  python scripts/coletar_ml.py               # coleta 5000 reviews (padrão)
  python scripts/coletar_ml.py --limite 100  # teste rápido com 100 reviews
  python scripts/coletar_ml.py --limite 500  # coleta média
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.config.settings import get_settings
from src.ingestion.mercadolivre import MercadoLivreIngestor, salvar

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main(limite: int) -> None:
    settings = get_settings()

    # Validar credenciais
    if not settings.ml_client_id or not settings.ml_client_secret:
        logger.error(
            "ML_CLIENT_ID e ML_CLIENT_SECRET não encontrados no .env\n"
            "Adicione as duas linhas ao arquivo .env na raiz do projeto."
        )
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("CCIS — Coleta Mercado Livre")
    logger.info("Limite: %d reviews", limite)
    logger.info("=" * 60)

    # Sobrescreve o limite das settings sem modificar o arquivo
    settings.__dict__["ml_reviews_por_coleta"] = limite

    ingestor = MercadoLivreIngestor()
    try:
        registros = await ingestor.fetch()
    finally:
        await ingestor.aclose()

    if not registros:
        logger.error("Nenhum registro coletado. Verifique as credenciais e a conexão.")
        sys.exit(1)

    caminho = salvar(registros)

    # Resumo final
    empresas  = len({r["seller_id"] for r in registros if r.get("seller_id")})
    com_texto = sum(1 for r in registros if len(r.get("texto", "")) >= 30)
    notas     = [r["nota_original"] for r in registros if r.get("nota_original")]
    media     = sum(notas) / len(notas) if notas else 0

    logger.info("")
    logger.info("=" * 60)
    logger.info("RESUMO DA COLETA")
    logger.info("  Reviews coletadas : %d", len(registros))
    logger.info("  Com texto útil    : %d", com_texto)
    logger.info("  Vendedores únicos : %d", empresas)
    logger.info("  Nota média        : %.2f ★", media)
    logger.info("  Arquivo salvo em  : %s", caminho)
    logger.info("=" * 60)
    logger.info("")
    logger.info("Próximo passo:")
    logger.info("  python scripts/classificar_ml.py --entrada %s", caminho)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coleta reviews do Mercado Livre")
    parser.add_argument(
        "--limite", type=int, default=5000,
        help="Número máximo de reviews a coletar (padrão: 5000)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.limite))
