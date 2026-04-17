"""Classificador direto (não-batch) para testes rápidos com poucos registros."""

from __future__ import annotations

import json
import time
from typing import Any

import anthropic
import structlog

from src.classification.prompts import SYSTEM_PROMPT, build_classification_prompt
from src.classification.schemas import ClassificationResult, ClassifiedComplaint, ComplaintRecord
from src.config.settings import get_settings

logger = structlog.get_logger(__name__)

# Configuração de retry
MAX_RETRIES = 5
INITIAL_BACKOFF = 5  # segundos
MAX_BACKOFF = 60  # segundos


class DirectClassifier:
    """Classifica reclamações usando a API regular do Claude (não-batch).

    Mais rápido para lotes pequenos (<50 registros). Inclui retry com
    backoff exponencial para lidar com erros 529 (Overloaded).
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)

    def classify(self, records: list[dict[str, Any]]) -> list[ClassifiedComplaint]:
        """Classifica registros um a um via API regular com retry."""
        complaints = [self._to_complaint(r) for r in records]
        results: list[ClassifiedComplaint] = []

        for i, complaint in enumerate(complaints):
            logger.info(
                "classificando",
                registro=i + 1,
                total=len(complaints),
                id=complaint.id,
                empresa=complaint.empresa,
            )

            result = self._classify_with_retry(complaint)
            results.append(result)

        sucesso = sum(1 for r in results if r.classification)
        erros = sum(1 for r in results if r.error)
        logger.info("classificacao_concluida", total=len(results), sucesso=sucesso, erros=erros)

        return results

    def _classify_with_retry(self, complaint: ComplaintRecord) -> ClassifiedComplaint:
        """Classifica um registro com retry e backoff exponencial."""
        backoff = INITIAL_BACKOFF

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                message = self._client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=512,
                    system=SYSTEM_PROMPT,
                    messages=[
                        {
                            "role": "user",
                            "content": build_classification_prompt(complaint.texto_anonimizado),
                        }
                    ],
                )

                classification = self._parse_response(message)

                if classification:
                    logger.info(
                        "classificado",
                        id=complaint.id,
                        categoria=classification.categoria,
                        severidade=classification.severidade,
                        confianca=classification.confianca,
                        tentativa=attempt,
                    )
                    return ClassifiedComplaint(record=complaint, classification=classification)
                else:
                    return ClassifiedComplaint(
                        record=complaint, error="Falha ao parsear resposta JSON"
                    )

            except (anthropic.APIStatusError,) as e:
                is_retryable = e.status_code in (429, 529, 500, 502, 503)

                if is_retryable and attempt < MAX_RETRIES:
                    logger.warning(
                        "retry_agendado",
                        id=complaint.id,
                        tentativa=attempt,
                        max_tentativas=MAX_RETRIES,
                        backoff_s=backoff,
                        status_code=e.status_code,
                    )
                    time.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF)
                    continue

                error_msg = f"API error (tentativa {attempt}/{MAX_RETRIES}): {e}"
                logger.warning("classificacao_falhou", id=complaint.id, error=error_msg)
                return ClassifiedComplaint(record=complaint, error=error_msg)

            except Exception as e:
                error_msg = f"Erro inesperado: {e}"
                logger.warning("classificacao_erro", id=complaint.id, error=error_msg)
                return ClassifiedComplaint(record=complaint, error=error_msg)

        # Fallback (shouldn't reach here)
        return ClassifiedComplaint(record=complaint, error="Max retries exceeded")

    def _parse_response(self, message: anthropic.types.Message) -> ClassificationResult | None:
        """Extrai e valida JSON da resposta do Claude."""
        text = ""
        try:
            text = message.content[0].text

            # Tenta extrair JSON do texto (pode vir com markdown code block)
            json_str = text
            if "```" in text or not text.strip().startswith("{"):
                start = text.find("{")
                end = text.rfind("}") + 1
                if start != -1 and end > start:
                    json_str = text[start:end]

            data = json.loads(json_str)
            return ClassificationResult(**data)
        except (json.JSONDecodeError, IndexError, KeyError, ValueError) as e:
            logger.warning("parse_erro", error=str(e), response_text=text[:200])
            return None

    @staticmethod
    def _to_complaint(record: dict[str, Any]) -> ComplaintRecord:
        """Converte dict de registro para ComplaintRecord."""
        texto = record.get("texto_reclamacao") or record.get("relato") or ""
        return ComplaintRecord(
            id=str(record.get("id", "")),
            texto_anonimizado=str(texto),
            fonte=str(record.get("fonte", "")),
            data_reclamacao=record.get("data_abertura"),
            empresa=record.get("nome_fantasia"),
            segmento=record.get("segmento_mercado"),
            assunto=record.get("assunto"),
        )
