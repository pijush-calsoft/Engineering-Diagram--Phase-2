"""The Model Gateway: the one path from blocks to hosted models (plan Phase 1; ADR-0005, ADR-0009).

Every call, in order:

1. Resolve the model for the role from configuration (OD-43); a role without a model fails.
2. Refuse images marked as client data until an image masking step exists (OD-39, OD-51).
3. Redact the instructions and every untrusted input (``redact.py``).
4. Screen untrusted inputs for prompt injection and wrap them as ``<data>`` (``guard.py``).
5. Refuse the call if the logged spend has reached ``EDP_LLM_BUDGET_USD`` (plan §4.1: budgets).
6. Call the backend; validate structured output against the caller's pydantic model.
7. Log the call with tokens, cost and flags, but no prompt text (``usage.py``).
"""

import base64
import hashlib
import json
import time
import uuid
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from edp_contracts import Flag
from edp_gateway import guard
from edp_gateway.backend import Backend, LiteLLMBackend
from edp_gateway.config import GatewayConfig
from edp_gateway.redact import Redactor
from edp_gateway.usage import CallRecord, UsageLog

Role = Literal["text", "vision", "code", "judge"]
DataClass = Literal["synthetic", "internal", "client"]


class GatewayError(RuntimeError):
    pass


class RoleNotConfigured(GatewayError):
    pass


class BudgetExceeded(GatewayError):
    pass


class ImageNotAllowed(GatewayError):
    pass


class OutputInvalid(GatewayError):
    pass


class Image(BaseModel):
    data: bytes
    mime: str = "image/png"


class CompletionRequest(BaseModel):
    service: str  # calling block or service, e.g. "b2_interpretation"
    role: Role
    instructions: str  # trusted: written in this repository, versioned below
    prompt_version: str
    inputs: list[str] = []  # untrusted: drawing text, notes, documents, earlier chat turns
    user: str | None = None  # the engineer's own request (console chat); redacted, not wrapped as data
    images: list[Image] = []
    data_class: DataClass  # where the inputs come from (OD-39)
    run_id: str | None = None
    max_output_tokens: int | None = None


class Usage(BaseModel):
    call_id: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    cost_source: str | None


class CompletionResult(BaseModel):
    text: str
    parsed: Any = None  # instance of the caller's output model, when one is given
    usage: Usage
    flags: list[Flag] = []


class EmbeddingResult(BaseModel):
    vectors: list[list[float]]
    usage: Usage
    flags: list[Flag] = []


class Gateway:
    def __init__(self, config: GatewayConfig, backend: Backend | None = None, usage: UsageLog | None = None):
        self.config = config
        self._backend = backend
        self.usage = usage or UsageLog(config.data_dir / "gateway" / "usage.sqlite")
        self._redact = Redactor(config.redact_terms)

    @property
    def backend(self) -> Backend:
        if self._backend is None:
            if not self.config.api_key:
                raise GatewayError("OPENAI_API_KEY is not set in the environment or .env")
            self._backend = LiteLLMBackend(self.config.api_key)
        return self._backend

    def _model(self, name: str) -> str:
        return f"{self.config.provider}/{name}"

    def _options(self) -> dict[str, Any]:
        return {"timeout": self.config.timeout_s, "num_retries": self.config.max_retries}

    def _check_budget(self) -> None:
        budget = self.config.budget_usd
        if budget is not None and self.usage.spent_usd() >= budget:
            raise BudgetExceeded(f"logged spend has reached EDP_LLM_BUDGET_USD ({budget:g} USD)")

    def complete(
        self, req: CompletionRequest, output_model: type[BaseModel] | None = None
    ) -> CompletionResult:
        call_id = uuid.uuid4().hex
        rec = CallRecord(
            call_id=call_id,
            service=req.service,
            run_id=req.run_id,
            kind="completion",
            role=req.role,
            prompt_version=req.prompt_version,
            data_class=req.data_class,
            status="refused",
        )
        try:
            name = self.config.models.get(req.role)
            if not name:
                raise RoleNotConfigured(
                    f"no model configured for role {req.role!r} (EDP_LLM_MODEL_{req.role.upper()})"
                )
            rec.model = self._model(name)
            if req.images and req.data_class == "client":
                raise ImageNotAllowed(
                    "client images need title-block masking before they may leave (OD-39, OD-51)"
                )
            kinds: Counter[str] = Counter()
            instructions = self._redact(req.instructions)
            kinds += instructions.kinds
            inputs = []
            for text in req.inputs:
                r = self._redact(text)
                kinds += r.kinds
                inputs.append(r.text)
            user = None
            if req.user is not None:
                u = self._redact(req.user)
                kinds += u.kinds
                user = u.text
            rec.redactions = dict(kinds)
            injection = sorted({name for text in inputs for name in guard.screen(text)})
            rec.flags = [f"PROMPT_INJECTION_SUSPECTED:{n}" for n in injection]
            messages = self._messages(instructions.text, inputs, req.images, user)
            rec.prompt_sha256 = hashlib.sha256(
                json.dumps(messages, sort_keys=True, default=str).encode()
            ).hexdigest()
            self._check_budget()
            options = self._options() | {"max_completion_tokens": req.max_output_tokens}
            if output_model is not None:
                options["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": output_model.__name__,
                        "schema": output_model.model_json_schema(),
                    },
                }
            rec.status = "error"
            started = time.perf_counter()
            reply = self.backend.complete(rec.model, messages, **options)
            rec.latency_ms = int((time.perf_counter() - started) * 1000)
            rec.model, rec.input_tokens, rec.output_tokens = (
                reply.model,
                reply.input_tokens,
                reply.output_tokens,
            )
            rec.cost_usd, rec.cost_source = reply.cost_usd, reply.cost_source
            parsed = None
            if output_model is not None:
                try:
                    parsed = output_model.model_validate_json(reply.text)
                except ValidationError as e:
                    raise OutputInvalid(
                        f"reply does not match {output_model.__name__}: {e.error_count()} error(s)"
                    ) from e
            rec.status = "ok"
            flags = self._flags(injection, rec)
            return CompletionResult(text=reply.text, parsed=parsed, usage=self._usage(rec), flags=flags)
        except Exception as e:
            rec.error = self._redact(f"{type(e).__name__}: {e}"[:300]).text
            raise
        finally:
            self.usage.record(rec)

    def embed(
        self, service: str, texts: list[str], data_class: DataClass, run_id: str | None = None
    ) -> EmbeddingResult:
        call_id = uuid.uuid4().hex
        rec = CallRecord(
            call_id=call_id,
            service=service,
            run_id=run_id,
            kind="embedding",
            role="embedding",
            data_class=data_class,
            status="refused",
        )
        try:
            if not self.config.embedding_model:
                raise RoleNotConfigured("no embedding model configured (EDP_EMBEDDING_MODEL)")
            rec.model = self._model(self.config.embedding_model)
            kinds: Counter[str] = Counter()
            clean = []
            for text in texts:
                r = self._redact(text)
                kinds += r.kinds
                clean.append(r.text)
            rec.redactions = dict(kinds)
            rec.prompt_sha256 = hashlib.sha256(json.dumps(clean).encode()).hexdigest()
            self._check_budget()
            rec.status = "error"
            started = time.perf_counter()
            reply = self.backend.embed(rec.model, clean, **self._options())
            rec.latency_ms = int((time.perf_counter() - started) * 1000)
            rec.model, rec.input_tokens = reply.model, reply.input_tokens
            rec.cost_usd, rec.cost_source = reply.cost_usd, reply.cost_source
            rec.status = "ok"
            return EmbeddingResult(vectors=reply.vectors, usage=self._usage(rec), flags=self._flags([], rec))
        except Exception as e:
            rec.error = self._redact(f"{type(e).__name__}: {e}"[:300]).text
            raise
        finally:
            self.usage.record(rec)

    @staticmethod
    def _messages(
        instructions: str, inputs: list[str], images: list[Image], user: str | None = None
    ) -> list[dict[str, Any]]:
        system = instructions if not inputs else f"{instructions}\n\n{guard.DATA_RULE}"
        content: list[dict[str, Any]] = []
        if inputs:
            content.append({"type": "text", "text": guard.wrap(inputs)})
        for img in images:
            url = f"data:{img.mime};base64,{base64.b64encode(img.data).decode()}"
            content.append({"type": "image_url", "image_url": {"url": url}})
        if user is not None:
            content.append({"type": "text", "text": user})
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        if content:
            messages.append({"role": "user", "content": content})
        return messages

    @staticmethod
    def _usage(rec: CallRecord) -> Usage:
        return Usage(
            call_id=rec.call_id,
            model=rec.model or "",
            input_tokens=rec.input_tokens,
            output_tokens=rec.output_tokens,
            cost_usd=rec.cost_usd,
            cost_source=rec.cost_source,
        )

    @staticmethod
    def _flags(injection: list[str], rec: CallRecord) -> list[Flag]:
        flags = [
            Flag(
                code="PROMPT_INJECTION_SUSPECTED",
                severity="review",
                message=f"input text matches injection pattern {name!r}; it was sent as data only",
            )
            for name in injection
        ]
        if rec.redactions:
            flags.append(
                Flag(
                    code="REDACTED",
                    severity="info",
                    message=f"removed before the call: {dict(sorted(rec.redactions.items()))}",
                )
            )
        if rec.cost_usd is None:
            flags.append(
                Flag(
                    code="COST_UNKNOWN",
                    severity="info",
                    message=f"{rec.model} is not in the LiteLLM cost map; tokens logged, cost not",
                )
            )
        return flags
