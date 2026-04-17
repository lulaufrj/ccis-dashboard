"""Ingestor de dados da Anvisa/Notivisa para cosmetovigilância.

Estratégia em 3 camadas (usa a primeira disponível):

1. **Registro de produtos** — DADOS_ABERTOS_COSMETICO.csv de dados.anvisa.gov.br
   Base de cosméticos registrados (referência para cruzamento).

2. **Importação manual Notivisa** — CSVs colocados em data/raw/notivisa/
   Dados de eventos adversos exportados por profissionais com acesso ao Notivisa,
   obtidos via LAI (Lei de Acesso à Informação) ou colaboração acadêmica.

3. **Alertas de segurança Anvisa** — Publicados em gov.br/anvisa
   Alertas de cosmetovigilância publicados pela Anvisa (dados públicos).

Referência regulatória:
- RDC 894/2024: cosmetovigilância obrigatória
- Lei 15.154/2025: cosméticos artesanais dispensados de registro
"""

from __future__ import annotations

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

# URLs para download do CSV de registro de cosméticos Anvisa
_ANVISA_CSV_URLS: list[str] = [
    "https://dados.anvisa.gov.br/dados/DADOS_ABERTOS_COSMETICO.csv",
    # Alternativa via portal dados.gov.br (redirecionamento)
    "https://dados.gov.br/dataset/produtos-de-higiene-perfumes-cosmeticos-e-saneantes-registrados-no-brasil-cosmeticos",
]

# Mapeamento de colunas do CSV de registros Anvisa → snake_case
_REGISTRO_COLUMN_MAP: dict[str, str] = {
    "PRODUTO_NOME": "nome_produto",
    "PRODUTO_CATEGORIA": "categoria_produto",
    "PRODUTO_SUBCATEGORIA": "subcategoria",
    "EMPRESA_NOME": "nome_empresa",
    "EMPRESA_CNPJ": "cnpj",
    "REGISTRO_NUMERO": "numero_registro",
    "REGISTRO_VALIDADE": "validade_registro",
    "REGISTRO_SITUACAO": "situacao_registro",
    "SITUACAO_REGISTRO": "situacao_registro",
    "CATEGORIA_REGULATORIA": "categoria_regulatoria",
    "PRODUTO": "nome_produto",
    "EMPRESA": "nome_empresa",
    "CNPJ": "cnpj",
    "PROCESSO": "processo",
    "REGISTRO": "numero_registro",
    "VALIDADE": "validade_registro",
}

# Mapeamento de colunas do Notivisa (exportação manual) → snake_case
# Baseado no dicionário de exportação do Notivisa e na literatura
_NOTIVISA_COLUMN_MAP: dict[str, str] = {
    # Campos comuns do Notivisa
    "Numero Notificacao": "numero_notificacao",
    "Número Notificação": "numero_notificacao",
    "Numero da Notificacao": "numero_notificacao",
    "Data Notificacao": "data_notificacao",
    "Data da Notificação": "data_notificacao",
    "Data Notificação": "data_notificacao",
    "Tipo Notificacao": "tipo_notificacao",
    "Tipo de Notificação": "tipo_notificacao",
    "Tipo Notificação": "tipo_notificacao",
    "Produto": "nome_produto",
    "Nome do Produto": "nome_produto",
    "Nome Produto": "nome_produto",
    "Empresa": "nome_empresa",
    "Fabricante": "nome_empresa",
    "Nome Empresa": "nome_empresa",
    "Empresa Fabricante": "nome_empresa",
    "Descricao": "descricao_evento",
    "Descrição": "descricao_evento",
    "Descrição do Evento": "descricao_evento",
    "Descricao Evento": "descricao_evento",
    "Relato": "descricao_evento",
    "Gravidade": "gravidade",
    "Grau de Gravidade": "gravidade",
    "Desfecho": "desfecho",
    "Resultado": "desfecho",
    "UF": "uf",
    "UF Notificador": "uf",
    "Estado": "uf",
    "Tipo Notificador": "tipo_notificador",
    "Fonte Notificacao": "tipo_notificador",
    "Categoria Produto": "categoria_produto",
    "Categoria": "categoria_produto",
    "Reacao": "reacao",
    "Reação": "reacao",
    "Tipo Reação": "reacao",
    "Tipo Reacao": "reacao",
    "Sinais Sintomas": "sinais_sintomas",
    "Sinais e Sintomas": "sinais_sintomas",
    "CNPJ": "cnpj",
    "Registro Anvisa": "numero_registro",
    "Lote": "lote",
    "Validade": "validade",
}

# Palavras-chave para filtrar cosméticos no CSV de registros
_COSMETIC_CATEGORIES: list[str] = [
    "cosmético",
    "cosmetico",
    "higiene pessoal",
    "perfume",
    "perfumaria",
    "grau 1",
    "grau 2",
    "grau i",
    "grau ii",
]

# Tipos de notificação que indicam eventos adversos (vs queixas técnicas)
_ADVERSE_EVENT_TYPES: list[str] = [
    "evento adverso",
    "ea",
    "reação adversa",
    "reacao adversa",
    "intoxicação",
    "intoxicacao",
]

_TECHNICAL_COMPLAINT_TYPES: list[str] = [
    "queixa técnica",
    "queixa tecnica",
    "qt",
    "desvio de qualidade",
]


def _normalize_notivisa_col(col: str) -> str:
    """Normaliza nome de coluna para snake_case."""
    # Tenta mapeamento direto primeiro
    if col in _NOTIVISA_COLUMN_MAP:
        return _NOTIVISA_COLUMN_MAP[col]
    if col in _REGISTRO_COLUMN_MAP:
        return _REGISTRO_COLUMN_MAP[col]

    # Fallback: normalização genérica
    result = col.strip().lower()
    result = re.sub(r"[áàãâ]", "a", result)
    result = re.sub(r"[éèê]", "e", result)
    result = re.sub(r"[íì]", "i", result)
    result = re.sub(r"[óòõô]", "o", result)
    result = re.sub(r"[úùü]", "u", result)
    result = re.sub(r"[ç]", "c", result)
    result = re.sub(r"\s+", "_", result)
    result = re.sub(r"[^\w]", "", result)
    return result


def _build_notivisa_text(record: dict[str, Any]) -> str:
    """Constrói texto descritivo a partir dos campos do Notivisa."""
    parts: list[str] = []

    # Tipo de notificação
    tipo = record.get("tipo_notificacao", "")
    if tipo and _is_valid(tipo):
        parts.append(f"Tipo: {tipo}")

    # Produto
    produto = record.get("nome_produto", "")
    if produto and _is_valid(produto):
        parts.append(f"Produto: {produto}")

    # Empresa
    empresa = record.get("nome_empresa", "")
    if empresa and _is_valid(empresa):
        parts.append(f"Empresa: {empresa}")

    # Descrição do evento (campo principal)
    descricao = record.get("descricao_evento", "")
    if descricao and _is_valid(descricao):
        parts.append(f"Descrição: {descricao}")

    # Reação
    reacao = record.get("reacao", "")
    if reacao and _is_valid(reacao):
        parts.append(f"Reação: {reacao}")

    # Sinais e sintomas
    sinais = record.get("sinais_sintomas", "")
    if sinais and _is_valid(sinais):
        parts.append(f"Sinais/Sintomas: {sinais}")

    # Gravidade
    gravidade = record.get("gravidade", "")
    if gravidade and _is_valid(gravidade):
        parts.append(f"Gravidade: {gravidade}")

    # Desfecho
    desfecho = record.get("desfecho", "")
    if desfecho and _is_valid(desfecho):
        parts.append(f"Desfecho: {desfecho}")

    # Categoria
    categoria = record.get("categoria_produto", "")
    if categoria and _is_valid(categoria):
        parts.append(f"Categoria: {categoria}")

    return " | ".join(parts) if parts else ""


def _build_registro_text(record: dict[str, Any]) -> str:
    """Constrói texto descritivo a partir dos campos do registro Anvisa."""
    parts: list[str] = []

    produto = record.get("nome_produto", "")
    if produto and _is_valid(produto):
        parts.append(f"Produto: {produto}")

    empresa = record.get("nome_empresa", "")
    if empresa and _is_valid(empresa):
        parts.append(f"Empresa: {empresa}")

    situacao = record.get("situacao_registro", "")
    if situacao and _is_valid(situacao):
        parts.append(f"Situação: {situacao}")

    categoria = record.get("categoria_regulatoria") or record.get("categoria_produto", "")
    if categoria and _is_valid(categoria):
        parts.append(f"Categoria: {categoria}")

    return " | ".join(parts) if parts else ""


def _is_valid(value: Any) -> bool:
    """Verifica se um valor é válido (não NaN, não vazio)."""
    s = str(value).strip()
    return bool(s) and s.lower() not in ("nan", "none", "null", "")


def _detect_file_type(df: pd.DataFrame) -> str:
    """Detecta se o CSV é de registros Anvisa ou exportação Notivisa.

    Retorna 'registro', 'notivisa', ou 'desconhecido'.
    """
    cols_lower = {c.lower() for c in df.columns}

    # Indicadores de registro Anvisa
    registro_indicators = {"situacao_registro", "categoria_regulatoria", "processo", "registro", "validade"}
    if len(cols_lower & registro_indicators) >= 2:
        return "registro"

    # Indicadores de Notivisa
    notivisa_indicators = {
        "tipo_notificacao", "descricao_evento", "gravidade", "desfecho",
        "reacao", "sinais_sintomas", "tipo_notificador", "numero_notificacao",
    }
    if len(cols_lower & notivisa_indicators) >= 2:
        return "notivisa"

    return "desconhecido"


class NotivisaIngestor(BaseIngestor):
    """Coleta dados de cosmetovigilância da Anvisa/Notivisa.

    Funciona em 3 modos complementares:
    1. Download do CSV de registros da Anvisa (dados abertos)
    2. Importação de CSVs do Notivisa colocados manualmente
    3. Ambos combinados

    Args:
        include_registros: Se True, baixa/processa a base de registros Anvisa.
        include_manual: Se True, processa CSVs em data/raw/notivisa/.
        filter_industrial: Se True, exclui empresas industriais.
    """

    def __init__(
        self,
        include_registros: bool = True,
        include_manual: bool = True,
        filter_industrial: bool = True,
    ) -> None:
        self._settings = get_settings()
        self._include_registros = include_registros
        self._include_manual = include_manual
        self._filter_industrial = filter_industrial
        self._blacklist = self._load_blacklist() if filter_industrial else []

        # Diretório para CSVs manuais do Notivisa
        self._notivisa_dir = self._settings.raw_dir / "notivisa"

    @property
    def source_name(self) -> str:
        return "notivisa_anvisa"

    async def fetch(self) -> list[dict[str, Any]]:
        """Coleta dados de todas as fontes configuradas."""
        all_records: list[dict[str, Any]] = []

        # Modo 1: Base de registros Anvisa
        if self._include_registros:
            logger.info("notivisa_modo_registros", ativo=True)
            registros = await self._fetch_registro_anvisa()
            all_records.extend(registros)

        # Modo 2: Importação manual de CSVs do Notivisa
        if self._include_manual:
            logger.info("notivisa_modo_manual", ativo=True, dir=str(self._notivisa_dir))
            manuais = self._process_manual_csvs()
            all_records.extend(manuais)

        logger.info(
            "notivisa_ingestao_completa",
            total_registros=len(all_records),
            fonte=self.source_name,
        )
        return all_records

    # ── Modo 1: Registro Anvisa ────────────────────────────────────────

    async def _fetch_registro_anvisa(self) -> list[dict[str, Any]]:
        """Baixa e processa o CSV de cosméticos registrados na Anvisa."""
        dest = self._settings.raw_dir / "DADOS_ABERTOS_COSMETICO.csv"

        if not dest.exists():
            downloaded = await self._download_anvisa_csv(dest)
            if not downloaded:
                logger.warning("anvisa_csv_indisponivel",
                    msg="CSV de registros não disponível. "
                        "Tente baixar manualmente de dados.anvisa.gov.br/dados/ "
                        "e colocar em: " + str(dest))
                return []
        else:
            logger.info("anvisa_csv_existente", path=str(dest))

        return self._parse_registro_csv(dest)

    async def _download_anvisa_csv(self, dest: Path) -> bool:
        """Tenta baixar o CSV de registros da Anvisa."""
        dest.parent.mkdir(parents=True, exist_ok=True)

        for url in _ANVISA_CSV_URLS:
            try:
                logger.info("tentando_download_anvisa", url=url)
                async with httpx.AsyncClient(
                    timeout=120,
                    follow_redirects=True,
                    verify=False,  # Anvisa tem problemas de SSL
                ) as client:
                    resp = await client.get(url)

                    # Verifica se é realmente um CSV (não uma página HTML)
                    content_type = resp.headers.get("content-type", "")
                    if resp.status_code == 200 and (
                        "csv" in content_type or
                        "text/plain" in content_type or
                        resp.content[:50].count(b";") > 2  # CSV separado por ;
                    ):
                        with open(dest, "wb") as f:
                            f.write(resp.content)
                        logger.info("anvisa_csv_baixado", path=str(dest),
                                    tamanho_mb=round(len(resp.content) / 1024 / 1024, 1))
                        return True

                    logger.warning("resposta_nao_csv", url=url, status=resp.status_code,
                                   content_type=content_type)

            except (httpx.HTTPError, httpx.ConnectError, Exception) as e:
                logger.warning("download_falhou", url=url, erro=str(e)[:200])

        return False

    def _parse_registro_csv(self, path: Path) -> list[dict[str, Any]]:
        """Parseia o CSV de registros Anvisa."""
        df = self._read_csv_auto(path)
        if df is None or df.empty:
            return []

        # Normaliza colunas
        df.columns = [_normalize_notivisa_col(c) for c in df.columns]

        logger.info("registro_anvisa_colunas", colunas=list(df.columns)[:15],
                     total_linhas=len(df))

        # Filtro: apenas registros com situação irregular ou cancelada
        # (registros ativos são normais, nos interessam os problemáticos)
        irregular_records: list[dict[str, Any]] = []

        if "situacao_registro" in df.columns:
            # Filtra situações que indicam problemas
            problematic_situations = ["cancelado", "suspenso", "caduc", "irregular"]
            mask = df["situacao_registro"].str.lower().str.contains(
                "|".join(problematic_situations), na=False
            )
            df_problems = df[mask]

            if not df_problems.empty:
                logger.info("registros_problematicos", quantidade=len(df_problems))
                records = df_problems.to_dict(orient="records")

                for record in records:
                    record["texto_reclamacao"] = _build_registro_text(record)
                    record["fonte"] = self.source_name
                    record["tipo_dado"] = "registro_irregular"

                    raw_id = (str(record.get("nome_produto", "")) +
                              str(record.get("nome_empresa", "")) +
                              str(record.get("numero_registro", "")))
                    record["id"] = hashlib.sha256(raw_id.encode()).hexdigest()[:16]

                irregular_records = records
            else:
                logger.info("nenhum_registro_problematico")
        else:
            logger.info("registro_sem_coluna_situacao", colunas=list(df.columns)[:20])

        # Também extrai estatísticas gerais para referência
        total_registros = len(df)
        logger.info("registro_anvisa_resumo",
                     total_registros=total_registros,
                     problematicos=len(irregular_records))

        return irregular_records

    # ── Modo 2: Importação Manual ──────────────────────────────────────

    def _process_manual_csvs(self) -> list[dict[str, Any]]:
        """Processa CSVs do Notivisa colocados manualmente no diretório."""
        if not self._notivisa_dir.exists():
            self._notivisa_dir.mkdir(parents=True, exist_ok=True)
            self._create_readme()
            logger.info(
                "diretorio_notivisa_criado",
                path=str(self._notivisa_dir),
                msg="Coloque CSVs exportados do Notivisa aqui.",
            )
            return []

        csv_files = list(self._notivisa_dir.glob("*.csv"))
        xlsx_files = list(self._notivisa_dir.glob("*.xlsx"))
        all_files = csv_files + xlsx_files

        # Ignora README
        all_files = [f for f in all_files if f.name != "LEIA-ME.txt"]

        if not all_files:
            logger.info(
                "nenhum_csv_notivisa",
                dir=str(self._notivisa_dir),
                msg="Nenhum arquivo encontrado. Coloque CSVs exportados do Notivisa aqui.",
            )
            return []

        all_records: list[dict[str, Any]] = []

        for file_path in all_files:
            logger.info("processando_notivisa_manual", arquivo=file_path.name)

            if file_path.suffix == ".xlsx":
                df = self._read_xlsx(file_path)
            else:
                df = self._read_csv_auto(file_path)

            if df is None or df.empty:
                logger.warning("arquivo_vazio_ou_invalido", path=str(file_path))
                continue

            # Normaliza colunas
            df.columns = [_normalize_notivisa_col(c) for c in df.columns]

            # Detecta tipo de arquivo
            file_type = _detect_file_type(df)
            logger.info("tipo_arquivo_detectado", arquivo=file_path.name, tipo=file_type)

            if file_type == "notivisa":
                records = self._process_notivisa_records(df, file_path.name)
            elif file_type == "registro":
                records = self._process_registro_records(df, file_path.name)
            else:
                # Tenta processar como Notivisa genérico
                logger.warning("tipo_desconhecido_tentando_generico", arquivo=file_path.name)
                records = self._process_generic_records(df, file_path.name)

            # Aplica filtro de blacklist se configurado
            if self._filter_industrial and self._blacklist:
                before = len(records)
                records = [
                    r for r in records
                    if not self._is_industrial(r.get("nome_empresa", ""))
                ]
                excluded = before - len(records)
                if excluded > 0:
                    logger.info("industriais_excluidas_notivisa",
                                excluidas=excluded, restantes=len(records))

            all_records.extend(records)
            logger.info("notivisa_manual_processado",
                        arquivo=file_path.name, registros=len(records))

        return all_records

    def _process_notivisa_records(
        self, df: pd.DataFrame, source_file: str
    ) -> list[dict[str, Any]]:
        """Processa registros do formato Notivisa (eventos adversos)."""
        records = df.to_dict(orient="records")
        processed: list[dict[str, Any]] = []

        for record in records:
            texto = _build_notivisa_text(record)
            if not texto:
                continue

            record["texto_reclamacao"] = texto
            record["fonte"] = self.source_name
            record["tipo_dado"] = "evento_adverso"
            record["arquivo_origem"] = source_file

            # Classifica tipo de notificação
            tipo = str(record.get("tipo_notificacao", "")).lower()
            if any(t in tipo for t in _ADVERSE_EVENT_TYPES):
                record["subtipo"] = "evento_adverso"
            elif any(t in tipo for t in _TECHNICAL_COMPLAINT_TYPES):
                record["subtipo"] = "queixa_tecnica"
            else:
                record["subtipo"] = "outro"

            # Mapeia gravidade Notivisa para severidade CCIS
            record["severidade_fonte"] = self._map_gravidade(
                record.get("gravidade", "")
            )

            # ID único
            raw_id = (texto + str(record.get("data_notificacao", "")) +
                      str(record.get("numero_notificacao", "")))
            record["id"] = hashlib.sha256(raw_id.encode()).hexdigest()[:16]

            processed.append(record)

        return processed

    def _process_registro_records(
        self, df: pd.DataFrame, source_file: str
    ) -> list[dict[str, Any]]:
        """Processa registros do formato Anvisa (base de registros)."""
        # Mesmo tratamento do Modo 1, mas vindo de arquivo manual
        records = df.to_dict(orient="records")
        processed: list[dict[str, Any]] = []

        for record in records:
            texto = _build_registro_text(record)
            if not texto:
                continue

            record["texto_reclamacao"] = texto
            record["fonte"] = self.source_name
            record["tipo_dado"] = "registro"
            record["arquivo_origem"] = source_file

            raw_id = (str(record.get("nome_produto", "")) +
                      str(record.get("nome_empresa", "")) +
                      str(record.get("numero_registro", "")))
            record["id"] = hashlib.sha256(raw_id.encode()).hexdigest()[:16]

            processed.append(record)

        return processed

    def _process_generic_records(
        self, df: pd.DataFrame, source_file: str
    ) -> list[dict[str, Any]]:
        """Processa registros de formato desconhecido — best effort."""
        records = df.to_dict(orient="records")
        processed: list[dict[str, Any]] = []

        for record in records:
            # Tenta construir texto a partir de qualquer campo disponível
            parts: list[str] = []
            for key, value in record.items():
                if value and _is_valid(value) and len(str(value)) > 3:
                    parts.append(f"{key}: {value}")

            texto = " | ".join(parts[:10])  # Limita a 10 campos
            if not texto:
                continue

            record["texto_reclamacao"] = texto
            record["fonte"] = self.source_name
            record["tipo_dado"] = "generico"
            record["arquivo_origem"] = source_file

            raw_id = texto[:200]
            record["id"] = hashlib.sha256(raw_id.encode()).hexdigest()[:16]

            processed.append(record)

        return processed

    # ── Utilitários ────────────────────────────────────────────────────

    def _read_csv_auto(self, path: Path) -> pd.DataFrame | None:
        """Lê CSV com auto-detecção de encoding e separador."""
        for encoding in ("utf-8", "latin-1", "cp1252"):
            for sep in (";", "\t", ",", "|"):
                try:
                    candidate = pd.read_csv(
                        path, sep=sep, encoding=encoding, dtype=str, nrows=5
                    )
                    if len(candidate.columns) >= 3:
                        return pd.read_csv(path, sep=sep, encoding=encoding, dtype=str)
                except (UnicodeDecodeError, pd.errors.ParserError):
                    continue
        logger.error("csv_leitura_falhou", path=str(path))
        return None

    def _read_xlsx(self, path: Path) -> pd.DataFrame | None:
        """Lê arquivo XLSX."""
        try:
            return pd.read_excel(path, dtype=str)
        except Exception as e:
            logger.error("xlsx_leitura_falhou", path=str(path), erro=str(e))
            return None

    def _load_blacklist(self) -> list[str]:
        """Carrega blacklist de empresas industriais."""
        path = self._settings.data_dir / "reference" / "empresas_industriais.txt"
        if not path.exists():
            return []

        terms: list[str] = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    terms.append(line.lower())
        return terms

    def _is_industrial(self, company_name: str) -> bool:
        """Verifica se empresa é industrial (usa word boundaries)."""
        if not company_name or not _is_valid(company_name):
            return False
        name_lower = str(company_name).strip().lower()
        for term in self._blacklist:
            pattern = r"\b" + re.escape(term) + r"\b"
            if re.search(pattern, name_lower):
                return True
        return False

    @staticmethod
    def _map_gravidade(gravidade: str) -> int:
        """Mapeia gravidade do Notivisa para severidade CCIS (1-5)."""
        if not gravidade or not _is_valid(gravidade):
            return 2  # default: Baixo

        g = str(gravidade).lower().strip()

        if any(x in g for x in ["grave", "óbito", "obito", "hospitalizaç", "internac"]):
            return 5  # Crítico
        if any(x in g for x in ["moderada", "moderado", "significat"]):
            return 4  # Alto
        if any(x in g for x in ["leve", "branda"]):
            return 3  # Médio
        if any(x in g for x in ["não grave", "nao grave", "sem"]):
            return 2  # Baixo

        return 2

    def _create_readme(self) -> None:
        """Cria README no diretório de importação manual."""
        readme_path = self._notivisa_dir / "LEIA-ME.txt"
        if readme_path.exists():
            return

        content = """\
DIRETÓRIO DE IMPORTAÇÃO MANUAL - NOTIVISA/ANVISA
=================================================

Coloque aqui os arquivos CSV ou XLSX exportados do sistema Notivisa
para que sejam processados automaticamente pelo pipeline CCIS.

COMO OBTER DADOS DO NOTIVISA:
1. Profissionais de saúde podem exportar dados via:
   https://www8.anvisa.gov.br/notivisa/frmLogin.asp

2. Solicitar via LAI (Lei de Acesso à Informação):
   https://falabr.cgu.gov.br/

3. Colaboração acadêmica com a Anvisa/GMON

FORMATOS ACEITOS:
- CSV (separadores: ; , \\t |)
- XLSX (Excel)

CAMPOS ESPERADOS (qualquer subconjunto):
- Número Notificação
- Data Notificação
- Tipo Notificação (Evento Adverso / Queixa Técnica)
- Produto / Nome do Produto
- Empresa / Fabricante
- Descrição do Evento / Relato
- Reação / Sinais e Sintomas
- Gravidade
- Desfecho
- UF
- Categoria do Produto

O sistema detecta automaticamente o formato e normaliza as colunas.
"""
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(content)
