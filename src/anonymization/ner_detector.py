"""Detector de entidades nomeadas (PII) via spaCy para português."""

from dataclasses import dataclass

import spacy
from spacy.language import Language

from src.config.settings import get_settings

# Labels de entidades que representam PII
_PII_LABELS: set[str] = {"PER", "PERSON", "LOC", "GPE"}

_PLACEHOLDER_MAP: dict[str, str] = {
    "PER": "[NOME_REMOVIDO]",
    "PERSON": "[NOME_REMOVIDO]",
    "LOC": "[LOCAL_REMOVIDO]",
    "GPE": "[LOCAL_REMOVIDO]",
}


@dataclass(frozen=True)
class Entity:
    """Entidade detectada pelo NER."""

    start: int
    end: int
    label: str
    placeholder: str


class NERDetector:
    """Detector de PII via Named Entity Recognition com spaCy."""

    def __init__(self, model: str | None = None) -> None:
        model_name = model or get_settings().spacy_model
        self._nlp: Language = spacy.load(model_name)

    def detect(self, text: str) -> list[Entity]:
        """Detecta entidades PII no texto.

        Returns:
            Lista de Entity com posições e labels das entidades encontradas.
        """
        doc = self._nlp(text)
        entities: list[Entity] = []

        for ent in doc.ents:
            if ent.label_ in _PII_LABELS:
                placeholder = _PLACEHOLDER_MAP.get(ent.label_, f"[{ent.label_}_REMOVIDO]")
                entities.append(
                    Entity(
                        start=ent.start_char,
                        end=ent.end_char,
                        label=ent.label_,
                        placeholder=placeholder,
                    )
                )

        return entities

    def replace(self, text: str) -> tuple[str, list[Entity]]:
        """Substitui entidades PII por placeholders.

        Returns:
            Tupla (texto_anonimizado, lista_de_entidades).
        """
        entities = self.detect(text)

        # Ordena do final para o início para manter posições válidas
        sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)

        result = text
        for ent in sorted_entities:
            result = result[: ent.start] + ent.placeholder + result[ent.end :]

        return result, entities
