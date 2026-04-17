"""Classe base abstrata para ingestores de dados."""

from abc import ABC, abstractmethod
from typing import Any


class BaseIngestor(ABC):
    """Interface que todo ingestor de dados deve implementar."""

    @abstractmethod
    async def fetch(self) -> list[dict[str, Any]]:
        """Coleta dados da fonte e retorna lista de registros normalizados."""
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Nome da fonte de dados (ex: 'consumidor_gov')."""
        ...
