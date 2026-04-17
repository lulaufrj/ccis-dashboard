"""Classificador de reclamações via Claude API Batch."""

from __future__ import annotations

import json
import time
from typing import Any

import anthropic
import structlog
from anthropic.types.messages import MessageBatch

from src.classification.prompts import SYSTEM_PROMPT, build_classification_prompt
from src.classification.schemas import ClassificationResult, ClassifiedComplaint, ComplaintRecord
from src.config.settings import get_settings

logger = structlog.get_logger(__name__)


class BatchClassifier:
    """Classifica reclamações cosméticas usando Claude API Message Batches."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)

    def classify(self, records: list[dict[str, Any]]) -> list[ClassifiedComplaint]:
        """Classifica uma lista de registros via Batch API.

        Divide em chunks de batch_size, envia cada batch, aguarda conclusão
        e retorna resultados validados com Pydantic.
        """
        complaints = [self._to_complaint(r) for r in records]
        results: list[ClassifiedComplaint] = []

        # Divide em chunks
        chunk_size = self._settings.batch_size
        chunks = [complaints[i : i + chunk_size] for i in range(0, len(complaints), chunk_size)]

        for i, chunk in enumerate(chunks):
            logger.info("batch_enviando", chunk=i + 1, total_chunks=len(chunks), size=len(chunk))

            batch_results = self._process_batch(chunk)
            results.extend(batch_results)

            logger.info(
                "batch_concluido",
                chunk=i + 1,
                sucesso=sum(1 for r in batch_results if r.classification),
                erros=sum(1 for r in batch_results if r.error),
            )

        return results

    def _process_batch(self, complaints: list[ComplaintRecord]) -> list[ClassifiedComplaint]:
        """Envia um batch, aguarda conclusão e retorna resultados."""
        # 1. Prepara requests (garante custom_id único com sufixo de índice)
        requests = []
        seen_ids: set[str] = set()
        for idx, complaint in enumerate(complaints):
            custom_id = complaint.id
            if custom_id in seen_ids:
                custom_id = f"{custom_id}_{idx}"
                complaint.id = custom_id
            seen_ids.add(custom_id)
            requests.append({
                "custom_id": custom_id,
                "params": {
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 512,
                    "system": SYSTEM_PROMPT,
                    "messages": [
                        {
                            "role": "user",
                            "content": build_classification_prompt(complaint.texto_anonimizado),
                        }
                    ],
                },
            })

        # 2. Cria batch
        batch = self._client.messages.batches.create(requests=requests)
        batch_id = batch.id
        logger.info("batch_criado", batch_id=batch_id)

        # 3. Poll até conclusão
        batch = self._poll_until_done(batch_id)

        # 4. Coleta resultados
        return self._collect_results(batch_id, complaints)

    def _poll_until_done(self, batch_id: str) -> MessageBatch:
        """Aguarda batch completar, com polling."""
        interval = self._settings.batch_poll_interval

        while True:
            batch = self._client.messages.batches.retrieve(batch_id)
            status = batch.processing_status

            counts = batch.request_counts
            logger.info(
                "batch_status",
                batch_id=batch_id,
                status=status,
                succeeded=counts.succeeded,
                errored=counts.errored,
                processing=counts.processing,
            )

            if status == "ended":
                return batch

            time.sleep(interval)

    def _collect_results(
        self, batch_id: str, complaints: list[ComplaintRecord]
    ) -> list[ClassifiedComplaint]:
        """Coleta e valida resultados do batch."""
        complaint_map = {c.id: c for c in complaints}
        results: list[ClassifiedComplaint] = []

        for entry in self._client.messages.batches.results(batch_id):
            custom_id = entry.custom_id
            complaint = complaint_map.get(custom_id)

            if not complaint:
                logger.warning("resultado_sem_registro", custom_id=custom_id)
                continue

            result = entry.result

            if result.type == "succeeded":
                classification = self._parse_response(result.message)
                results.append(
                    ClassifiedComplaint(record=complaint, classification=classification)
                )
            elif result.type == "errored":
                error_msg = f"API error: {result.error.type} - {result.error.message}"
                logger.warning("classificacao_falhou", id=custom_id, error=error_msg)
                results.append(ClassifiedComplaint(record=complaint, error=error_msg))
            else:
                # canceled ou expired
                error_msg = f"Batch result: {result.type}"
                logger.warning("classificacao_falhou", id=custom_id, error=error_msg)
                results.append(ClassifiedComplaint(record=complaint, error=error_msg))

        # Registros sem resposta
        responded_ids = {r.record.id for r in results}
        for complaint in complaints:
            if complaint.id not in responded_ids:
                results.append(
                    ClassifiedComplaint(record=complaint, error="Sem resposta no batch")
                )

        return results

    def _parse_response(self, message: anthropic.types.Message) -> ClassificationResult | None:
        """Extrai e valida JSON da resposta do Claude."""
        text = ""
        try:
            text = message.content[0].text

            # Tenta extrair JSON do texto (pode vir com markdown code block)
            json_str = text
            if "```" in text or text.strip().startswith("{") is False:
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
        # Usa texto_reclamacao (campo construído pelo ingestor) ou fallback para relato
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
