"""Classifica reviews do Mercado Livre via Claude Batch API.

Fluxo:
  1. Lê reviews_YYYY-MM-DD.json de data/raw/mercadolivre/
  2. Mapeia schema ML → ComplaintRecord
  3. (Opcional) Anonimiza textos (reviews geralmente têm pouco PII)
  4. Classifica via Claude Batch (50% desconto vs API direta)
  5. Mescla resultados em data/classified/classificados.json

Uso:
  python scripts/classificar_ml.py                          # usa arquivo mais recente
  python scripts/classificar_ml.py --entrada PATH           # arquivo específico
  python scripts/classificar_ml.py --limite 100             # apenas primeiros 100
  python scripts/classificar_ml.py --direto                 # usa DirectClassifier (teste rápido)
  python scripts/classificar_ml.py --sem-anonimizacao       # pula anonimização
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import structlog

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.anonymization.anonymizer import Anonymizer
from src.classification.batch_classifier import BatchClassifier
from src.classification.direct_classifier import DirectClassifier
from src.config.settings import get_settings

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
)
logger = structlog.get_logger("classificar_ml")


def ml_para_complaint(review: dict) -> dict:
    """Converte um review ML para o formato esperado pelo classificador.

    Injeta contexto do produto/nota no texto para ajudar o Claude a
    classificar corretamente (ex.: nota 1★ + texto curto = reclamação).
    """
    nota = review.get("nota_original")
    texto = (review.get("texto") or "").strip()
    produto = review.get("produto", "")
    preco = review.get("preco")

    # Monta texto enriquecido para a classificação
    partes: list[str] = []
    if produto:
        partes.append(f"Produto: {produto}")
    if nota is not None:
        partes.append(f"Avaliação: {nota}/5 estrelas")
    if preco:
        partes.append(f"Preço: R$ {preco}")
    partes.append(f"Comentário do consumidor: {texto}")
    texto_completo = " | ".join(partes)

    return {
        "id":                review["id"],
        "fonte":             "mercadolivre",
        "texto_reclamacao":  texto_completo,
        "data_abertura":     review.get("data_reclamacao"),
        "nome_fantasia":     review.get("empresa"),
        "segmento_mercado":  "Higiene Pessoal, Perfumaria e Cosméticos",
        "assunto":           produto,
        # Campos extras de ML preservados para o dashboard
        "_ml_nota":          nota,
        "_ml_preco":         preco,
        "_ml_item_id":       review.get("item_id"),
        "_ml_seller_id":     review.get("seller_id"),
        "_ml_categoria":     review.get("categoria_ml"),
        "_ml_seller_nivel":  review.get("seller_nivel"),
        "_ml_seller_status": review.get("seller_power_status"),
        "_ml_seller_vendas": review.get("seller_total_vendas"),
    }


def _arquivo_mais_recente() -> Path:
    """Retorna o JSON de reviews ML mais recente."""
    raw_dir = get_settings().raw_dir / "mercadolivre"
    arquivos = sorted(raw_dir.glob("reviews_*.json"))
    if not arquivos:
        logger.error("nenhum_arquivo_ml_encontrado", dir=str(raw_dir))
        sys.exit(1)
    return arquivos[-1]


def main(
    entrada: Path,
    limite: int | None,
    usar_batch: bool,
    anonimizar: bool,
) -> None:
    settings = get_settings()

    if not settings.anthropic_api_key:
        logger.error("sem_chave_api", motivo="ANTHROPIC_API_KEY não configurada no .env")
        sys.exit(1)

    # === FASE 1: Carregar reviews ML ===
    logger.info("=== FASE 1: CARREGAMENTO ===", arquivo=str(entrada))
    with open(entrada, encoding="utf-8") as f:
        reviews = json.load(f)
    if limite:
        reviews = reviews[:limite]
    logger.info("reviews_carregados", total=len(reviews))

    registros = [ml_para_complaint(r) for r in reviews]

    # Guardar campos extras ML para reinjetar após classificação
    extras_por_id = {r["id"]: {k: v for k, v in r.items() if k.startswith("_ml_")}
                     for r in registros}

    # === FASE 2: Anonimização ===
    if anonimizar:
        logger.info("=== FASE 2: ANONIMIZAÇÃO ===")
        anonymizer = Anonymizer()
        registros = anonymizer.anonymize_batch(registros)
        logger.info("anonimizados", total=len(registros))
    else:
        logger.info("anonimizacao_pulada")
        # BatchClassifier espera texto_anonimizado no dict
        for r in registros:
            r.setdefault("texto_anonimizado", r.get("texto_reclamacao", ""))

    # === FASE 3: Classificação ===
    modo = "Batch API (50% desconto)" if usar_batch else "API direta (Sonnet)"
    logger.info("=== FASE 3: CLASSIFICAÇÃO ===", modo=modo)
    classifier = BatchClassifier() if usar_batch else DirectClassifier()
    results = classifier.classify(registros)

    classificados_novos: list[dict] = []
    for r in results:
        entry = r.record.model_dump()
        if r.classification:
            entry["classificacao"] = r.classification.model_dump()
        if r.error:
            entry["erro_classificacao"] = r.error
        # Reinjetar campos extras ML
        entry.update(extras_por_id.get(entry.get("id", ""), {}))
        classificados_novos.append(entry)

    # === FASE 4: Mesclar com classificados existentes ===
    logger.info("=== FASE 4: MESCLAGEM ===")
    path_classificados = settings.classified_dir / "classificados.json"
    existentes: list[dict] = []
    if path_classificados.exists():
        with open(path_classificados, encoding="utf-8") as f:
            existentes = json.load(f)
        logger.info("existentes_carregados", total=len(existentes))

    por_id = {r.get("id"): r for r in existentes}
    for r in classificados_novos:
        por_id[r.get("id")] = r
    mesclados = list(por_id.values())

    settings.classified_dir.mkdir(parents=True, exist_ok=True)
    with open(path_classificados, "w", encoding="utf-8") as f:
        json.dump(mesclados, f, ensure_ascii=False, indent=2)

    # === Resumo ===
    cat: dict[str, int] = {}
    sev: dict[int, int] = {}
    fonte: dict[str, int] = {}
    for r in mesclados:
        cls = r.get("classificacao") or {}
        c = cls.get("categoria", "N/A")
        s = cls.get("severidade", 0)
        f = r.get("fonte", "N/A")
        cat[c] = cat.get(c, 0) + 1
        sev[s] = sev.get(s, 0) + 1
        fonte[f] = fonte.get(f, 0) + 1

    logger.info(
        "=== RESUMO FINAL ===",
        total=len(mesclados),
        por_fonte=fonte,
        categorias=cat,
        severidades=sev,
        arquivo=str(path_classificados),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Classifica reviews ML via Claude")
    parser.add_argument("--entrada", type=str, default="",
                        help="Caminho para reviews_YYYY-MM-DD.json (padrão: arquivo mais recente)")
    parser.add_argument("--limite", type=int, default=None,
                        help="Processar apenas os N primeiros reviews (para teste)")
    parser.add_argument("--direto", action="store_true",
                        help="Usar DirectClassifier ao invés do BatchClassifier (teste)")
    parser.add_argument("--sem-anonimizacao", action="store_true",
                        help="Pular anonimização (reviews ML têm pouco PII)")
    args = parser.parse_args()

    entrada = Path(args.entrada) if args.entrada else _arquivo_mais_recente()

    main(
        entrada=entrada,
        limite=args.limite,
        usar_batch=not args.direto,
        anonimizar=not args.sem_anonimizacao,
    )
