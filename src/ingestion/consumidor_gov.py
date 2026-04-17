"""Ingestor de reclamações do Consumidor.gov.br via portal CKAN."""

import hashlib
import re
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import structlog

from src.config.settings import get_settings
from src.ingestion.base import BaseIngestor

logger = structlog.get_logger(__name__)

# Mapeamento de colunas conhecidas → snake_case normalizado
# Os CSVs variam entre anos (38 cols em 2014-2018, 20-30 em 2019+)
_COLUMN_MAP: dict[str, str] = {
    "Região": "regiao",
    "Regi\xe3o": "regiao",
    "UF": "uf",
    "Cidade": "cidade",
    "Sexo": "sexo",
    "Faixa Etária": "faixa_etaria",
    "Faixa Et\xe1ria": "faixa_etaria",
    "Data Finalização": "data_finalizacao",
    "Data Finaliza\xe7\xe3o": "data_finalizacao",
    "Data Abertura": "data_abertura",
    "Tempo Resposta": "tempo_resposta",
    "Nome Fantasia": "nome_fantasia",
    "Segmento de Mercado": "segmento_mercado",
    "Área": "area",
    "\xc1rea": "area",
    "Assunto": "assunto",
    "Grupo Problema": "grupo_problema",
    "Problema": "problema",
    "Como Comprou Contratou": "como_comprou",
    "Procurou Empresa": "procurou_empresa",
    "Respondida": "respondida",
    "Situação": "situacao",
    "Situa\xe7\xe3o": "situacao",
    "Avaliação Reclamação": "avaliacao",
    "Avalia\xe7\xe3o Reclama\xe7\xe3o": "avaliacao",
    "Nota do Consumidor": "nota_consumidor",
    "Relato": "relato",
    "Resposta": "resposta",
    "Ano Abertura": "ano_abertura",
    "Mês Abertura": "mes_abertura",
    "M\xeas Abertura": "mes_abertura",
    "Gestor": "gestor",
    "Canal de Origem": "canal_origem",
}

# Termos para detectar segmento cosmético via substring
_COSMETIC_KEYWORDS: list[str] = [
    "cosm",
    "perfumar",
    "higiene pessoal",
]

# Grupos do Consumidor.gov.br classificáveis deterministicamente como Comercial
_GRUPOS_COMERCIAL: frozenset[str] = frozenset({
    "Cobrança / Contestação",
    "Entrega do Produto",
    "Contrato / Oferta",
    "Atendimento / SAC",
    "Dados Pessoais e Privacidade",
})


def _normalize_col(col: str) -> str:
    """Converte nome de coluna para snake_case."""
    if col in _COLUMN_MAP:
        return _COLUMN_MAP[col]
    col = col.strip().lower()
    col = re.sub(r"[áàãâ]", "a", col)
    col = re.sub(r"[éèê]", "e", col)
    col = re.sub(r"[íì]", "i", col)
    col = re.sub(r"[óòõô]", "o", col)
    col = re.sub(r"[úùü]", "u", col)
    col = re.sub(r"[ç]", "c", col)
    col = re.sub(r"\s+", "_", col)
    col = re.sub(r"[^\w]", "", col)
    return col


def _load_industrial_blacklist() -> list[str]:
    """Carrega lista de empresas industriais a serem excluídas.

    Lê de data/reference/empresas_industriais.txt. Cada linha é um termo
    de busca (case-insensitive, substring match). Linhas com # são ignoradas.
    """
    settings = get_settings()
    path = settings.data_dir / "reference" / "empresas_industriais.txt"

    if not path.exists():
        logger.warning("blacklist_nao_encontrada", path=str(path))
        return []

    terms: list[str] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                terms.append(line.lower())

    logger.info("blacklist_carregada", termos=len(terms))
    return terms


def _is_industrial(company_name: str, blacklist: list[str]) -> bool:
    """Verifica se empresa é industrial (deve ser excluída).

    Usa word boundaries para evitar falsos positivos (ex: 'natura' não deve
    matchar 'naturais' ou 'natural').
    """
    if not company_name or str(company_name).strip().lower() == "nan":
        return False
    name_lower = str(company_name).strip().lower()
    for term in blacklist:
        # Word boundary regex: match apenas se for palavra inteira
        pattern = r"\b" + re.escape(term) + r"\b"
        if re.search(pattern, name_lower):
            return True
    return False


def _build_complaint_text(record: dict[str, Any]) -> str:
    """Constrói texto da reclamação a partir dos campos disponíveis.

    O CSV aberto do Consumidor.gov.br nem sempre inclui a coluna 'Relato'
    (texto livre). Quando ausente, concatenamos os campos descritivos.
    """
    # Se tiver o campo Relato, usar direto
    relato = record.get("relato")
    if relato and str(relato).strip() and str(relato).strip().lower() != "nan":
        return str(relato).strip()

    # Construir texto sintético a partir de campos descritivos
    parts: list[str] = []

    empresa = record.get("nome_fantasia", "")
    if empresa and str(empresa).strip().lower() != "nan":
        parts.append(f"Empresa: {empresa}")

    assunto = record.get("assunto", "")
    if assunto and str(assunto).strip().lower() != "nan":
        parts.append(f"Assunto: {assunto}")

    grupo = record.get("grupo_problema", "")
    if grupo and str(grupo).strip().lower() != "nan":
        parts.append(f"Grupo do problema: {grupo}")

    problema = record.get("problema", "")
    if problema and str(problema).strip().lower() != "nan":
        parts.append(f"Problema: {problema}")

    area = record.get("area", "")
    if area and str(area).strip().lower() != "nan":
        parts.append(f"Área: {area}")

    avaliacao = record.get("avaliacao", "")
    if avaliacao and str(avaliacao).strip().lower() != "nan":
        parts.append(f"Avaliação: {avaliacao}")

    return " | ".join(parts) if parts else ""


def _should_classify_with_api(record: dict[str, Any]) -> bool:
    """Decide se um registro precisa ser classificado pela API da Claude.

    Aplica regras determinísticas antes de qualquer chamada de rede:
    1. Se o grupo do problema é explicitamente Comercial → não precisa API.
    2. Se o grupo indica qualidade/saúde/segurança → sempre precisa API.
    3. Para grupos ambíguos, verifica keywords de risco no texto.

    Args:
        record: Dicionário normalizado com campos do Consumidor.gov.br.

    Returns:
        True se o registro deve ser enviado para a API Claude; False caso
        possa ser classificado deterministicamente como Comercial.
    """
    from src.prefilter.risk_keywords import (
        GRUPOS_COMERCIAL_DETERMINISTICO,
        GRUPOS_PRECISA_API,
        RISK_KEYWORDS,
    )

    # Encontra o valor de grupo_problema tolerando variações de mojibake
    grupo: str = ""
    for key, value in record.items():
        if "grupo" in key.lower():
            raw = str(value).strip()
            if raw and raw.lower() != "nan":
                grupo = raw
                break

    # Regra 1 — grupo explicitamente Comercial
    if grupo in GRUPOS_COMERCIAL_DETERMINISTICO:
        texto = str(record.get("texto_reclamacao", "")).lower()
        # Mesmo em grupo Comercial, se o texto contiver keyword de risco
        # pode ser um relato de reação com problema logístico associado
        for kw in RISK_KEYWORDS:
            if kw in texto:
                return True
        return False

    # Regra 2 — grupo explicitamente precisa API
    if grupo in GRUPOS_PRECISA_API:
        return True

    # Regra 3 — grupo ambíguo: verificar texto por keywords de risco
    texto = str(record.get("texto_reclamacao", "")).lower()
    for kw in RISK_KEYWORDS:
        if kw in texto:
            return True

    # Sem grupo reconhecido e sem keywords → tratar como Comercial
    return False


def _classify_deterministic(record: dict[str, Any]) -> dict[str, Any] | None:
    """Retorna classificação pré-preenchida quando não é necessária a API.

    Deve ser chamado somente quando ``_should_classify_with_api`` retorna
    ``False``. Gera um resultado de categoria Comercial com confiança máxima.

    Args:
        record: Dicionário normalizado com campos do Consumidor.gov.br.

    Returns:
        Dict com chaves ``classificacao`` e ``classificado_localmente``, ou
        ``None`` se o grupo não puder ser determinado.
    """
    grupo: str = ""
    for key, value in record.items():
        if "grupo" in key.lower():
            raw = str(value).strip()
            if raw and raw.lower() != "nan":
                grupo = raw
                break

    return {
        "classificacao": {
            "categoria": "Comercial",
            "severidade": 1,
            "confianca": 1.0,
            "justificativa": f"Classificado deterministicamente pelo grupo: {grupo}",
            "palavras_chave": [],
        },
        "classificado_localmente": True,
    }


class ConsumidorGovIngestor(BaseIngestor):
    """Coleta reclamações do Consumidor.gov.br via dados abertos CKAN."""

    def __init__(self, max_csvs: int = 5, filter_industrial: bool = True) -> None:
        self._settings = get_settings()
        self._max_csvs = max_csvs
        self._filter_industrial = filter_industrial
        self._blacklist = _load_industrial_blacklist() if filter_industrial else []

    @property
    def source_name(self) -> str:
        return "consumidor_gov"

    async def fetch(self) -> list[dict[str, Any]]:
        """Descobre CSVs no CKAN, baixa e retorna registros filtrados."""
        csv_urls = await self._discover_csv_urls()
        if not csv_urls:
            logger.warning("nenhum_csv_encontrado", dataset=self._settings.ckan_dataset_id)
            return []

        # Limita ao número mais recente de CSVs
        if len(csv_urls) > self._max_csvs:
            logger.info(
                "limitando_csvs",
                total_disponivel=len(csv_urls),
                baixando=self._max_csvs,
            )
            csv_urls = csv_urls[-self._max_csvs :]

        self._settings.raw_dir.mkdir(parents=True, exist_ok=True)

        all_records: list[dict[str, Any]] = []
        total_before_filter = 0
        total_industrial_excluded = 0

        for url, name in csv_urls:
            dest = self._settings.raw_dir / name
            if not dest.exists():
                await self._download_csv(url, dest)
            else:
                logger.info("csv_ja_existe", path=str(dest))

            records, n_before, n_excluded = self._parse_and_filter(dest)
            total_before_filter += n_before
            total_industrial_excluded += n_excluded

            logger.info(
                "csv_processado",
                arquivo=name,
                cosmeticos_total=n_before,
                industriais_excluidas=n_excluded,
                artesanais_mantidas=len(records),
            )
            all_records.extend(records)

        logger.info(
            "ingestao_completa",
            total_cosmeticos=total_before_filter,
            industriais_excluidas=total_industrial_excluded,
            artesanais_restantes=len(all_records),
            fonte=self.source_name,
        )
        return all_records

    async def _discover_csv_urls(self) -> list[tuple[str, str]]:
        """Consulta API CKAN para obter URLs dos recursos CSV."""
        url = (
            f"{self._settings.ckan_base_url}/api/3/action/package_show"
            f"?id={self._settings.ckan_dataset_id}"
        )
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        resources = data.get("result", {}).get("resources", [])
        csv_resources: list[tuple[str, str]] = []

        for r in resources:
            fmt = (r.get("format") or "").upper()
            if fmt == "CSV":
                res_url = r.get("url", "")
                name = r.get("name", "") or r.get("description", "") or "unknown"
                safe_name = re.sub(r"[^\w\-.]", "_", name)
                if not safe_name.endswith(".csv"):
                    safe_name += ".csv"
                csv_resources.append((res_url, safe_name))

        logger.info("csvs_descobertos", quantidade=len(csv_resources))
        return csv_resources

    async def _download_csv(self, url: str, dest: Path) -> None:
        """Baixa CSV com streaming para lidar com arquivos grandes."""
        logger.info("baixando_csv", url=url, destino=str(dest))
        async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with open(dest, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
        logger.info("csv_baixado", destino=str(dest))

    def _parse_and_filter(self, path: Path) -> tuple[list[dict[str, Any]], int, int]:
        """Lê CSV, normaliza colunas, filtra por cosméticos e exclui industriais.

        Returns:
            Tupla (registros_filtrados, total_cosmeticos, industriais_excluidas).
        """
        # Tenta diferentes combinações de encoding e separador
        df: pd.DataFrame | None = None
        for encoding in ("utf-8", "latin-1", "cp1252"):
            for sep in (";", "\t", ","):
                try:
                    candidate = pd.read_csv(
                        path, sep=sep, encoding=encoding, dtype=str, nrows=5
                    )
                    if len(candidate.columns) >= 5:
                        df = pd.read_csv(path, sep=sep, encoding=encoding, dtype=str)
                        break
                except (UnicodeDecodeError, pd.errors.ParserError):
                    continue
            if df is not None:
                break

        if df is None or df.empty:
            logger.error("erro_leitura_csv", path=str(path))
            return [], 0, 0

        # Normaliza nomes de colunas
        df.columns = [_normalize_col(c) for c in df.columns]

        # FILTRO 1: Segmento cosmético
        if "segmento_mercado" in df.columns:
            mask = df["segmento_mercado"].str.lower().str.contains(
                "|".join(_COSMETIC_KEYWORDS), na=False
            )
            df_cosmetic = df[mask]
        else:
            logger.warning("sem_coluna_segmento", colunas=list(df.columns))
            df_cosmetic = df.head(0)

        total_cosmetics = len(df_cosmetic)

        if df_cosmetic.empty:
            return [], 0, 0

        # FILTRO 2: Excluir empresas industriais (blacklist)
        n_excluded = 0
        if self._filter_industrial and self._blacklist and "nome_fantasia" in df_cosmetic.columns:
            is_ind = df_cosmetic["nome_fantasia"].apply(
                lambda x: _is_industrial(x, self._blacklist)
            )
            n_excluded = is_ind.sum()
            df_filtered = df_cosmetic[~is_ind]
        else:
            df_filtered = df_cosmetic

        if df_filtered.empty:
            return [], total_cosmetics, n_excluded

        # Converte para registros e enriquece
        records = df_filtered.to_dict(orient="records")
        for record in records:
            record["texto_reclamacao"] = _build_complaint_text(record)

            raw_id = str(record.get("texto_reclamacao", "")) + str(
                record.get("data_abertura", "")
            )
            record["id"] = hashlib.sha256(raw_id.encode()).hexdigest()[:16]
            record["fonte"] = self.source_name

            # Hash do texto normalizado para deduplicação cross-run
            texto_norm = str(record.get("texto_reclamacao", "")).lower().strip()
            record["hash_texto"] = hashlib.sha256(
                texto_norm.encode("utf-8")
            ).hexdigest()[:32]

            # Normaliza grupo_problema para uso nos filtros
            grupo_val: str = ""
            for key, value in record.items():
                if "grupo" in key.lower():
                    raw = str(value).strip()
                    if raw and raw.lower() != "nan":
                        grupo_val = raw
                        break
            record["grupo_problema"] = grupo_val

            # Decide se precisa API ou pode ser classificado deterministicamente
            precisa_api = _should_classify_with_api(record)
            record["precisa_api"] = precisa_api

            if not precisa_api:
                # Injeta classificação Comercial determinística
                det = _classify_deterministic(record)
                if det:
                    record["classificado_localmente"] = det["classificado_localmente"]
                    record["classificacao"] = det["classificacao"]

        return records, total_cosmetics, n_excluded
