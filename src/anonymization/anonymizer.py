"""Pipeline de anonimização combinando regex + spaCy NER."""

from dataclasses import dataclass, field
from typing import Any

import structlog

from src.anonymization.audit_log import AnonymizationAuditLogger
from src.anonymization.ner_detector import NERDetector
from src.anonymization.regex_patterns import detect_pii_regex

logger = structlog.get_logger(__name__)

# Campos textuais que devem ser anonimizados em cada registro
_TEXT_FIELDS: list[str] = ["texto_reclamacao", "relato", "resposta", "nome_fantasia"]


@dataclass
class AnonymizationResult:
    """Resultado da anonimização de um texto."""

    text: str
    detections: list[dict[str, str | int]] = field(default_factory=list)
    total_pii_found: int = 0


class Anonymizer:
    """Pipeline de anonimização: regex (determinístico) → NER (heurístico)."""

    def __init__(self) -> None:
        self._ner = NERDetector()
        self._audit = AnonymizationAuditLogger()

    def anonymize(self, text: str) -> AnonymizationResult:
        """Anonimiza um texto removendo PII com regex + NER.

        A ordem é: regex primeiro (padrões determinísticos como CPF, email),
        depois NER (nomes, locais). Overlaps são resolvidos mantendo a
        detecção que começa primeiro.
        """
        if not text or not text.strip():
            return AnonymizationResult(text=text)

        # 1. Coleta detecções de ambas as fontes
        regex_detections = detect_pii_regex(text)
        ner_entities = self._ner.detect(text)

        ner_detections: list[dict[str, str | int]] = [
            {
                "label": e.label,
                "start": e.start,
                "end": e.end,
                "placeholder": e.placeholder,
            }
            for e in ner_entities
        ]

        # 2. Merge e resolve overlaps
        all_detections = self._resolve_overlaps(regex_detections + ner_detections)

        # 3. Substitui do final para o início
        all_detections.sort(key=lambda d: int(d["start"]), reverse=True)

        result = text
        for det in all_detections:
            start = int(det["start"])
            end = int(det["end"])
            result = result[:start] + str(det["placeholder"]) + result[end:]

        return AnonymizationResult(
            text=result,
            detections=all_detections,
            total_pii_found=len(all_detections),
        )

    def anonymize_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Anonimiza campos textuais de um registro."""
        result = dict(record)
        record_id = str(record.get("id", "unknown"))

        for field_name in _TEXT_FIELDS:
            value = record.get(field_name)
            if not value or not isinstance(value, str):
                continue

            anon = self.anonymize(value)
            result[field_name] = anon.text

            self._audit.log_detections(
                record_id=record_id,
                field=field_name,
                detections=anon.detections,
            )

        return result

    def anonymize_batch(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Anonimiza uma lista de registros."""
        results: list[dict[str, Any]] = []
        total_pii = 0

        for i, record in enumerate(records):
            anon_record = self.anonymize_record(record)
            results.append(anon_record)

            if (i + 1) % 100 == 0:
                logger.info("anonimizacao_progresso", processados=i + 1, total=len(records))

        for r in results:
            for f in _TEXT_FIELDS:
                # Conta PII nos campos originais para log
                orig = records[results.index(r)].get(f, "")
                if orig and isinstance(orig, str):
                    total_pii += len(detect_pii_regex(orig))

        logger.info(
            "anonimizacao_completa",
            registros=len(results),
            total_pii_detectado=total_pii,
        )
        return results

    @staticmethod
    def _resolve_overlaps(
        detections: list[dict[str, str | int]],
    ) -> list[dict[str, str | int]]:
        """Remove detecções sobrepostas, mantendo a que começa primeiro."""
        if not detections:
            return []

        sorted_dets = sorted(detections, key=lambda d: (int(d["start"]), -int(d["end"])))

        resolved: list[dict[str, str | int]] = [sorted_dets[0]]
        for det in sorted_dets[1:]:
            last = resolved[-1]
            if int(det["start"]) >= int(last["end"]):
                resolved.append(det)

        return resolved
