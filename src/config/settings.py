"""Configurações centralizadas do CCIS via Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Resolve o caminho absoluto do .env a partir da raiz do projeto
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"

# Carrega .env com override=True para que valores do arquivo tenham prioridade
# sobre variáveis de ambiente vazias herdadas do sistema
load_dotenv(_ENV_FILE, override=True)


class Settings(BaseSettings):
    """Configurações do CCIS carregadas de variáveis de ambiente."""

    # Claude API
    anthropic_api_key: str = ""

    # Banco de dados (MVP: SQLite; produção: PostgreSQL)
    database_url: str = "sqlite:///data/ccis.db"

    # Diretórios
    data_dir: Path = _PROJECT_ROOT / "data"

    # spaCy
    spacy_model: str = "pt_core_news_lg"

    # Claude Batch API
    batch_size: int = 50
    batch_poll_interval: int = 30  # segundos entre polls

    # Logging
    log_level: str = "INFO"
    environment: str = "development"

    # Consumidor.gov.br
    ckan_base_url: str = "https://dados.mj.gov.br"
    ckan_dataset_id: str = "reclamacoes-do-consumidor-gov-br"

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def anonymized_dir(self) -> Path:
        return self.data_dir / "anonymized"

    @property
    def classified_dir(self) -> Path:
        return self.data_dir / "classified"


@lru_cache
def get_settings() -> Settings:
    """Retorna instância cacheada das configurações."""
    return Settings()
