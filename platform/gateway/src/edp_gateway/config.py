"""Gateway settings from the environment and the local ``.env`` (OD-2: runs locally).

Real environment variables win over ``.env``. Blank values are open decisions, not defaults
(see ``.env.example``): a blank model makes that role unavailable, a blank budget means no
limit, a blank timeout or retry count leaves LiteLLM's own default (OD-50).

The API key is read here and handed only to the model backend. It is never logged,
returned or shown in ``repr``.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

ROLES = ("text", "vision", "code", "judge")  # OD-43: EDP_LLM_MODEL_TEXT, _VISION, _CODE, _JUDGE


def read_env_file(path: Path) -> dict[str, str]:
    """``KEY=value`` lines; ``#`` comments and blank lines ignored; surrounding quotes removed."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _optional_float(value: str) -> float | None:
    return float(value) if value else None


@dataclass(frozen=True)
class GatewayConfig:
    api_key: str = field(repr=False)
    provider: str
    models: dict[str, str]  # role -> model name; only roles with a model
    embedding_model: str | None
    budget_usd: float | None
    redact_terms: tuple[str, ...] = field(repr=False)  # client names stay out of logs and reprs
    timeout_s: float | None
    max_retries: int | None
    data_dir: Path

    @classmethod
    def load(cls, env_file: Path | None = None) -> "GatewayConfig":
        path = env_file or Path(os.environ.get("EDP_ENV_FILE", ".env"))
        env = read_env_file(path) | {k: v for k, v in os.environ.items() if k.startswith(("EDP_", "OPENAI_"))}

        def get(key: str) -> str:
            return env.get(key, "").strip()

        retries = get("EDP_LLM_MAX_RETRIES")
        return cls(
            api_key=get("OPENAI_API_KEY"),
            provider=get("EDP_LLM_PROVIDER") or "openai",  # OD-37: OpenAI is the only provider
            models={r: get(f"EDP_LLM_MODEL_{r.upper()}") for r in ROLES if get(f"EDP_LLM_MODEL_{r.upper()}")},
            embedding_model=get("EDP_EMBEDDING_MODEL") or None,
            budget_usd=_optional_float(get("EDP_LLM_BUDGET_USD")),
            redact_terms=tuple(t.strip() for t in get("EDP_REDACT_TERMS").split(",") if t.strip()),
            timeout_s=_optional_float(get("EDP_LLM_TIMEOUT_S")),
            max_retries=int(retries) if retries else None,
            data_dir=Path(get("EDP_DATA_DIR") or "var"),
        )
