"""Classificador eficiente: Haiku 4.5 + prompt caching + chunking + dedupe.

Otimizações empilhadas para atingir ~US$ 0,80 / 1.500 registros:
- claude-haiku-4-5 (3× mais barato que Sonnet)
- Prompt caching no system prompt (-85% nos tokens de input repetidos)
- Chunking de 5 registros por chamada API (amortiza overhead por chamada)
- temperature=0 + max_tokens mínimo (saída enxuta)
- Retry com backoff exponencial para 429/5xx
- Pula registros já classificados (dedupe por hash)
- Pula registros com classificação determinística local (Comercial)
"""

from __future__ import annotations

import json
import time
from typing import Any

import anthropic
import structlog

from src.classification.prompts import SYSTEM_PROMPT
from src.classification.schemas import (
    ClassificationResult,
    ClassifiedComplaint,
    ComplaintRecord,
)
from src.config.settings import get_settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constantes de tuning
# ---------------------------------------------------------------------------
CHUNK_SIZE: int = 5          # registros por chamada API
MAX_RETRIES: int = 3         # tentativas antes de desistir do chunk
INITIAL_BACKOFF: int = 5     # segundos iniciais para backoff exponencial

# ---------------------------------------------------------------------------
# Template de chunking — classifica N reclamações por chamada
# ---------------------------------------------------------------------------
CHUNK_TEMPLATE = """\
Classifique as {n} reclamações sobre cosméticos abaixo.

{reclamacoes}

Responda com um JSON array com exatamente {n} objetos, na mesma ordem:
[
  {{
    "idx": 0,
    "categoria": "Segurança" | "Qualidade" | "Eficácia" | "Comercial",
    "severidade": 1-5,
    "confianca": 0.0-1.0,
    "justificativa": "explicação breve",
    "palavras_chave": ["termo1", "termo2"]
  }},
  ...
]
Retorne APENAS o array JSON, sem markdown, sem texto adicional."""


class EfficientClassifier:
    """Classificador otimizado para custo mínimo com Claude Haiku 4.5.

    Attributes:
        _settings: Configurações do projeto (inclui chave API).
        _client: Cliente Anthropic SDK.
        _already_classified: Conjunto de hashes de registros já classificados
            (usados para deduplicate entre execuções).

    Example::

        classifier = EfficientClassifier(already_classified_hashes=hashes_existentes)
        results = classifier.classify(registros)
    """

    def __init__(self, already_classified_hashes: set[str] | None = None) -> None:
        self._settings = get_settings()
        self._client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)
        self._already_classified: set[str] = already_classified_hashes or set()

    def classify(self, records: list[dict[str, Any]]) -> list[ClassifiedComplaint]:
        """Classifica lista de registros com todas as otimizações aplicadas.

        Separa registros em três grupos:
        1. Já classificados localmente (Comercial determinístico) — retorno imediato.
        2. Duplicatas de execução anterior (por hash_texto) — ignorados.
        3. Precisam de API — enviados em chunks para Claude Haiku 4.5.

        Args:
            records: Lista de dicionários com campos de reclamação, podendo
                incluir ``classificado_localmente``, ``classificacao`` e
                ``hash_texto`` gerados pelo ingestor.

        Returns:
            Lista de :class:`ClassifiedComplaint` com resultado de classificação
            ou mensagem de erro por registro.
        """
        complaints = [self._to_complaint(r) for r in records]

        local_results: list[ClassifiedComplaint] = []
        needs_api: list[tuple[int, ComplaintRecord]] = []  # (idx_original, complaint)

        for i, (r, c) in enumerate(zip(records, complaints)):
            if r.get("classificado_localmente") and r.get("classificacao"):
                # Usar classificação determinística sem chamar API
                cls_data = r["classificacao"]
                try:
                    cls = ClassificationResult(**cls_data)
                    local_results.append(ClassifiedComplaint(record=c, classification=cls))
                except Exception:
                    needs_api.append((i, c))
            elif c.id in self._already_classified:
                logger.info("dedupe_skip", id=c.id)
                # Não adiciona a nenhuma lista — será descartado silenciosamente
            else:
                needs_api.append((i, c))

        n_deduped = len(complaints) - len(local_results) - len(needs_api)
        logger.info(
            "classificacao_inicio",
            total=len(complaints),
            local=len(local_results),
            api=len(needs_api),
            deduped=n_deduped,
        )

        # Processar em chunks via API
        api_results: list[ClassifiedComplaint] = []
        for chunk_start in range(0, len(needs_api), CHUNK_SIZE):
            chunk = needs_api[chunk_start : chunk_start + CHUNK_SIZE]
            chunk_complaints = [c for _, c in chunk]
            results = self._classify_chunk_with_retry(chunk_complaints)
            api_results.extend(results)

        all_results = local_results + api_results

        sucesso = sum(1 for r in all_results if r.classification)
        erros = sum(1 for r in all_results if r.error)
        logger.info(
            "classificacao_concluida",
            total=len(all_results),
            sucesso=sucesso,
            erros=erros,
        )

        return all_results

    # ------------------------------------------------------------------
    # Métodos internos
    # ------------------------------------------------------------------

    def _classify_chunk_with_retry(
        self, complaints: list[ComplaintRecord]
    ) -> list[ClassifiedComplaint]:
        """Classifica um chunk de até ``CHUNK_SIZE`` reclamações com retry.

        Usa backoff exponencial para erros 429/5xx e faz fallback para
        classificação individual em caso de parse failure persistente.

        Args:
            complaints: Registros a classificar neste chunk.

        Returns:
            Lista de :class:`ClassifiedComplaint` (um por registro do chunk).
        """
        backoff = INITIAL_BACKOFF

        reclamacoes_text = "\n\n".join(
            f"[{i}] {c.texto_anonimizado[:600]}"
            for i, c in enumerate(complaints)
        )
        user_content = CHUNK_TEMPLATE.format(
            n=len(complaints),
            reclamacoes=reclamacoes_text,
        )

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                message = self._client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=300 * len(complaints),  # ~300 tokens por resultado
                    temperature=0,
                    system=[
                        {
                            "type": "text",
                            "text": SYSTEM_PROMPT,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[{"role": "user", "content": user_content}],
                )

                results = self._parse_chunk_response(message, complaints)
                if results is not None:
                    logger.info(
                        "chunk_classificado",
                        chunk_size=len(complaints),
                        tentativa=attempt,
                        input_tokens=message.usage.input_tokens,
                        output_tokens=message.usage.output_tokens,
                        cache_read=getattr(
                            message.usage, "cache_read_input_tokens", 0
                        ),
                    )
                    return results

                # Parse falhou — fallback individual
                logger.warning(
                    "chunk_parse_falhou",
                    tentativa=attempt,
                    chunk_size=len(complaints),
                )
                if len(complaints) > 1:
                    return [
                        r
                        for c in complaints
                        for r in self._classify_chunk_with_retry([c])
                    ]
                return [
                    ClassifiedComplaint(
                        record=c, error="Falha ao parsear resposta"
                    )
                    for c in complaints
                ]

            except anthropic.APIStatusError as e:
                if e.status_code in (429, 529, 500, 502, 503) and attempt < MAX_RETRIES:
                    logger.warning(
                        "retry",
                        attempt=attempt,
                        status=e.status_code,
                        backoff=backoff,
                    )
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60)
                    continue
                return [
                    ClassifiedComplaint(record=c, error=str(e)) for c in complaints
                ]

            except Exception as e:
                return [
                    ClassifiedComplaint(record=c, error=str(e)) for c in complaints
                ]

        return [
            ClassifiedComplaint(record=c, error="Max retries exceeded")
            for c in complaints
        ]

    def _parse_chunk_response(
        self,
        message: anthropic.types.Message,
        complaints: list[ComplaintRecord],
    ) -> list[ClassifiedComplaint] | None:
        """Parseia resposta JSON array do chunk.

        Lida com markdown extra (blocos ```json) e extrai o array mesmo que
        o modelo insira texto antes ou depois.

        Args:
            message: Resposta da API Anthropic.
            complaints: Registros do chunk (para associar resultados em ordem).

        Returns:
            Lista de :class:`ClassifiedComplaint` ou ``None`` se o parse falhar.
        """
        text = ""
        try:
            text = message.content[0].text.strip()

            # Limpar possível markdown
            if "```" in text:
                start = text.find("[")
                end = text.rfind("]") + 1
                if start != -1 and end > start:
                    text = text[start:end]
            elif not text.startswith("["):
                start = text.find("[")
                if start != -1:
                    text = text[start:]

            data = json.loads(text)
            if not isinstance(data, list) or len(data) != len(complaints):
                logger.warning(
                    "chunk_tamanho_incorreto",
                    esperado=len(complaints),
                    recebido=len(data) if isinstance(data, list) else "nao_lista",
                )
                return None

            results: list[ClassifiedComplaint] = []
            for item, complaint in zip(data, complaints):
                item.pop("idx", None)
                cls = ClassificationResult(**item)
                results.append(ClassifiedComplaint(record=complaint, classification=cls))
            return results

        except (json.JSONDecodeError, KeyError, ValueError, IndexError) as e:
            logger.warning(
                "parse_erro",
                error=str(e),
                text_preview=text[:200] if text else "",
            )
            return None

    @staticmethod
    def _to_complaint(record: dict[str, Any]) -> ComplaintRecord:
        """Converte dicionário bruto para :class:`ComplaintRecord`.

        Tolera nomes alternativos de campos (``texto_anonimizado`` vs
        ``texto_reclamacao``, ``data_abertura`` vs ``data_reclamacao``, etc.).

        Args:
            record: Dicionário com campos do registro de reclamação.

        Returns:
            Instância de :class:`ComplaintRecord`.
        """
        texto = record.get("texto_anonimizado") or record.get("texto_reclamacao") or ""
        return ComplaintRecord(
            id=str(record.get("id", "")),
            texto_anonimizado=str(texto),
            fonte=str(record.get("fonte", "")),
            data_reclamacao=record.get("data_abertura") or record.get("data_reclamacao"),
            empresa=record.get("nome_fantasia") or record.get("empresa"),
            segmento=record.get("segmento_mercado"),
            assunto=record.get("assunto"),
        )
