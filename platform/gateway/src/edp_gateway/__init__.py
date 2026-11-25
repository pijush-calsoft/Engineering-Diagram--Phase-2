"""Model Gateway (plan Phase 1): the one path from blocks to hosted models (ADR-0005, ADR-0009)."""

from edp_gateway.config import GatewayConfig
from edp_gateway.gateway import (
    BudgetExceeded,
    CompletionRequest,
    CompletionResult,
    EmbeddingResult,
    Gateway,
    GatewayError,
    Image,
    ImageNotAllowed,
    OutputInvalid,
    RoleNotConfigured,
)

__all__ = [
    "BudgetExceeded",
    "CompletionRequest",
    "CompletionResult",
    "EmbeddingResult",
    "Gateway",
    "GatewayConfig",
    "GatewayError",
    "Image",
    "ImageNotAllowed",
    "OutputInvalid",
    "RoleNotConfigured",
]
