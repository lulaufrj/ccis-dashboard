"""Log de auditoria para anonimização — registra detecções sem conteúdo original."""

import json
from datetime import datetime, timezone
from pathlib import Path

import structlog

from src.config.settings import get_settings

logger = structlog.get_logger(__name__)


class AnonymizationAuditLogger:
    """Registra eventos de anonimização para conformidade LGPD.

    Grava em JSONL: tipo de PII, posição e placeholder — nunca o conteúdo original.
    """

    def __init__(self, log_path: Path | None = None) -> None:
        settings = get_settings()
        self._log_path = log_path or (settings.anonymized_dir / "audit_log.jsonl")
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_detections(
        self,
        record_id: str,
        field: str,
        detections: list[dict[str, str | int]],
    ) -> None:
        """Registra detecções de PII para um campo de um registro.

        Args:
            record_id: ID do registro processado.
            field: Nome do campo anonimizado (ex: 'relato').
            detections: Lista de detecções com label, start, end, placeholder.
        """
        if not detections:
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "record_id": record_id,
            "field": field,
            "total_detections": len(detections),
            "types": [
                {
                    "label": str(d.get("label", "")),
                    "position_start": int(d.get("start", 0)),
                    "position_end": int(d.get("end", 0)),
                    "placeholder": str(d.get("placeholder", "")),
                }
                for d in detections
            ],
        }

        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.debug(
            "auditoria_anonimizacao",
            record_id=record_id,
            field=field,
            detections=len(detections),
        )
