"""Model backend: LiteLLM as an in-process library (plan §4.1: LiteLLM, MIT).

The plan runs the LiteLLM *proxy*; the POC has no containers or separate services (OD-21),
so the gateway calls the LiteLLM SDK directly (ADR-0009). Costs come from the model cost map
bundled with the installed LiteLLM version, which ``uv.lock`` pins; the map is never fetched
from the network (``LITELLM_LOCAL_MODEL_COST_MAP``), so a cost is reproducible.
"""

import os
from dataclasses import dataclass
from importlib.metadata import version
from typing import Any, Protocol


@dataclass
class Reply:
    text: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    cost_source: str | None


@dataclass
class EmbeddingReply:
    vectors: list[list[float]]
    model: str
    input_tokens: int | None
    cost_usd: float | None
    cost_source: str | None


class Backend(Protocol):
    def complete(self, model: str, messages: list[dict[str, Any]], **options: Any) -> Reply: ...
    def embed(self, model: str, texts: list[str], **options: Any) -> EmbeddingReply: ...


class LiteLLMBackend:
    def __init__(self, api_key: str):
        os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
        import litellm  # imported late: slow, and it reads the variable above at import

        litellm.suppress_debug_info = True
        if hasattr(litellm, "telemetry"):
            litellm.telemetry = False
        self._litellm = litellm
        self._key = api_key
        self._cost_source = f"litellm {version('litellm')} bundled model cost map"

    def _cost(self, response: Any) -> float | None:
        cost = (getattr(response, "_hidden_params", None) or {}).get("response_cost")
        if cost is None:
            try:
                cost = self._litellm.completion_cost(completion_response=response)
            except Exception:  # noqa: BLE001 - a model missing from the cost map has no cost
                return None
        return float(cost)

    def complete(self, model: str, messages: list[dict[str, Any]], **options: Any) -> Reply:
        response = self._litellm.completion(
            model=model,
            messages=messages,
            api_key=self._key,
            **{k: v for k, v in options.items() if v is not None},
        )
        usage = getattr(response, "usage", None)
        cost = self._cost(response)
        return Reply(
            text=response.choices[0].message.content or "",
            model=getattr(response, "model", model),
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            cost_usd=cost,
            cost_source=self._cost_source if cost is not None else None,
        )

    def embed(self, model: str, texts: list[str], **options: Any) -> EmbeddingReply:
        response = self._litellm.embedding(
            model=model, input=texts, api_key=self._key, **{k: v for k, v in options.items() if v is not None}
        )
        usage = getattr(response, "usage", None)
        cost = self._cost(response)
        return EmbeddingReply(
            vectors=[list(d["embedding"]) for d in response.data],
            model=getattr(response, "model", model),
            input_tokens=getattr(usage, "prompt_tokens", None),
            cost_usd=cost,
            cost_source=self._cost_source if cost is not None else None,
        )
