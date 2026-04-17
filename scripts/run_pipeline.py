"""Pipeline completo: Ingestão → Anonimização → Classificação."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import structlog

# Adiciona raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.anonymization.anonymizer import Anonymizer
from src.classification.batch_classifier import BatchClassifier
from src.classification.direct_classifier import DirectClassifier
from src.config.settings import get_settings
from src.ingestion.consumidor_gov import ConsumidorGovIngestor
from src.ingestion.dou import DOUIngestor
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

logger = structlog.get_logger("pipeline")


async def run_ingestion(
    skip_download: bool,
    include_industrial: bool = False,
    source: str = "consumidor_gov",
) -> list[dict]:
    """Fase 1: Ingestão de dados da(s) fonte(s) selecionada(s).

    Args:
        skip_download: Reutilizar arquivos já baixados.
        include_industrial: Se True, não exclui empresas industriais.
        source: 'consumidor_gov', 'notivisa', 'dou', 'todos'.
    """
    filter_industrial = not include_industrial
    records: list[dict] = []

    if source in ("consumidor_gov", "ambos", "todos"):
        logger.info("fonte_selecionada", fonte="consumidor_gov")
        records.extend(
            await _fetch_consumidor_gov(skip_download, filter_industrial)
        )

    if source in ("notivisa", "ambos", "todos"):
        logger.info("fonte_selecionada", fonte="notivisa")
        records.extend(await _fetch_notivisa(skip_download, filter_industrial))

    if source in ("dou", "todos"):
        logger.info("fonte_selecionada", fonte="dou")
        records.extend(await _fetch_dou(filter_industrial))

    return records


async def _fetch_consumidor_gov(
    skip_download: bool, filter_industrial: bool
) -> list[dict]:
    """Ingestão do Consumidor.gov.br."""
    settings = get_settings()

    if skip_download:
        raw_dir = settings.raw_dir
        if not raw_dir.exists() or not list(raw_dir.glob("*.csv")):
            logger.error("nenhum_csv_encontrado", dir=str(raw_dir))
            return []

        logger.info("reusando_csvs", dir=str(raw_dir))
        ingestor = ConsumidorGovIngestor(filter_industrial=filter_industrial)
        records: list[dict] = []
        # Só processa CSVs do Consumidor.gov.br (não o Anvisa)
        for csv_path in raw_dir.glob("*.csv"):
            if "DADOS_ABERTOS_COSMETICO" in csv_path.name:
                continue  # pertence ao Notivisa
            filtered, _total, _excluded = ingestor._parse_and_filter(csv_path)
            records.extend(filtered)
        return records

    ingestor = ConsumidorGovIngestor(filter_industrial=filter_industrial)
    return await ingestor.fetch()


async def _fetch_notivisa(skip_download: bool, filter_industrial: bool) -> list[dict]:
    """Ingestão Notivisa/Anvisa (3 modos: registros + manual)."""
    # skip_download não aplica aqui — Notivisa usa cache automático + CSVs manuais
    ingestor = NotivisaIngestor(
        include_registros=True,
        include_manual=True,
        filter_industrial=filter_industrial,
    )
    return await ingestor.fetch()


async def _fetch_dou(filter_industrial: bool) -> list[dict]:
    """Ingestão DOU/Anvisa (alertas, recalls, interdições)."""
    ingestor = DOUIngestor(
        max_per_query=20,
        filter_industrial=filter_industrial,
        fetch_full_text=False,
    )
    return await ingestor.fetch()


def run_anonymization(records: list[dict]) -> list[dict]:
    """Fase 2: Anonimização de PII com spaCy + regex."""
    anonymizer = Anonymizer()
    return anonymizer.anonymize_batch(records)


def run_classification(records: list[dict], use_direct: bool = False) -> list[dict]:
    """Fase 3: Classificação via Claude API.

    Args:
        records: Registros anonimizados.
        use_direct: Se True, usa API regular (rápido, para <50 registros).
                    Se False, usa Batch API (econômico, para grandes volumes).
    """
    if use_direct:
        logger.info("usando_api_direta", motivo="Mais rápido para poucos registros")
        classifier = DirectClassifier()
    else:
        logger.info("usando_batch_api", motivo="Econômico para grandes volumes")
        classifier = BatchClassifier()
    results = classifier.classify(records)

    output: list[dict] = []
    for r in results:
        entry = r.record.model_dump()
        if r.classification:
            entry["classificacao"] = r.classification.model_dump()
        if r.error:
            entry["erro_classificacao"] = r.error
        output.append(entry)

    return output


def save_results(records: list[dict], output_dir: Path, stage: str) -> Path:
    """Salva registros em JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{stage}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    logger.info("resultados_salvos", path=str(output_path), registros=len(records))
    return output_path


async def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline CCIS — Fase 1 MVP")
    parser.add_argument("--skip-download", action="store_true", help="Reusar CSVs já baixados")
    parser.add_argument("--limit", type=int, default=0, help="Limitar número de registros (0=todos)")
    parser.add_argument(
        "--skip-classification",
        action="store_true",
        help="Pular classificação (útil para testar ingestão + anonimização)",
    )
    parser.add_argument(
        "--include-industrial",
        action="store_true",
        help="Incluir empresas industriais (Natura, Avon, etc). Padrão: apenas artesanais.",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Usar API direta (não-batch). Mais rápido para poucos registros.",
    )
    parser.add_argument(
        "--source",
        choices=["consumidor_gov", "notivisa", "dou", "ambos", "todos"],
        default="consumidor_gov",
        help=(
            "Fonte de dados (padrão: consumidor_gov). "
            "'ambos' = consumidor_gov+notivisa; 'todos' = todas as fontes."
        ),
    )
    args = parser.parse_args()

    settings = get_settings()

    # === FASE 1: Ingestão ===
    logger.info("=== FASE 1: INGESTÃO ===", fonte=args.source)
    if not args.include_industrial:
        logger.info("filtro_ativo", modo="Excluindo empresas industriais (foco: artesanais)")
    records = await run_ingestion(
        args.skip_download, args.include_industrial, source=args.source
    )

    if not records:
        logger.error("pipeline_abortado", motivo="nenhum registro ingerido")
        return

    if args.limit > 0:
        records = records[: args.limit]
        logger.info("registros_limitados", limite=args.limit)

    logger.info("ingestao_concluida", total=len(records))

    # === FASE 2: Anonimização ===
    logger.info("=== FASE 2: ANONIMIZAÇÃO ===")
    anonymized = run_anonymization(records)
    save_results(anonymized, settings.anonymized_dir, "anonimizados")

    # === FASE 3: Classificação ===
    if args.skip_classification:
        logger.info("classificacao_pulada")
    elif not settings.anthropic_api_key:
        logger.error(
            "classificacao_pulada_sem_chave",
            motivo="ANTHROPIC_API_KEY não configurada no .env",
        )
        logger.info("Edite o arquivo .env e insira sua chave: ANTHROPIC_API_KEY=sk-ant-...")
    else:
        logger.info("=== FASE 3: CLASSIFICAÇÃO ===")
        # Usa API direta se flag --direct ou se poucos registros (<50)
        use_direct = args.direct or len(anonymized) < 50
        classified = run_classification(anonymized, use_direct=use_direct)
        save_results(classified, settings.classified_dir, "classificados")

        # Resumo
        categorias: dict[str, int] = {}
        severidades: dict[int, int] = {}
        for r in classified:
            cls = r.get("classificacao", {})
            if cls:
                cat = cls.get("categoria", "N/A")
                sev = cls.get("severidade", 0)
                categorias[cat] = categorias.get(cat, 0) + 1
                severidades[sev] = severidades.get(sev, 0) + 1

        logger.info(
            "=== RESUMO ===",
            total_processados=len(classified),
            categorias=categorias,
            severidades=severidades,
        )

    logger.info("pipeline_concluido")


if __name__ == "__main__":
    asyncio.run(main())
