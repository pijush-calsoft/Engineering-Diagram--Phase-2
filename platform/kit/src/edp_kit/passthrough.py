"""Pass-through results for domain-specific blocks (added 2026-11-26).

Blocks 4 to 8 need a domain pack: templates, material cards, load cases and report templates
are specific to a component family (deck slide 34). A run names its pack in its parameters,
``{"domain_pack": "construction"}``, the way the deck's design spec names ``domain:`` (deck
slide 20). Without one, or when an upstream block was skipped, a domain block passes the run
through: it returns ``ok`` with placeholder outputs that carry the inputs' source locators, as
the Phase 1 stubs did, so runs of other families still complete.
"""

from edp_contracts import Artifact, BlockRequest, BlockResult, Flag, SourceLocator

SKIPPED_SCHEME = "skipped://"
PLACEHOLDER_SCHEMES = (SKIPPED_SCHEME, "stub://")


def domain_pack(req: BlockRequest) -> str | None:
    value = req.params.get("domain_pack")
    return str(value) if value else None


def is_placeholder(artifact: Artifact) -> bool:
    return artifact.uri.startswith(PLACEHOLDER_SCHEMES)


def skip_reason(req: BlockRequest) -> str | None:
    """Why a domain block should pass this run through, or None to run it."""
    if domain_pack(req) is None:
        return "the run names no domain pack"
    if any(is_placeholder(a) for a in req.inputs):
        return "an upstream block was skipped"
    return None


def pass_through(block_name: str, produces: set[str], req: BlockRequest, reason: str) -> BlockResult:
    sources: list[SourceLocator] = []
    for a in req.inputs:
        sources.extend(s for s in a.sources if s not in sources)
    outputs = [
        Artifact(
            kind=k,
            uri=f"{SKIPPED_SCHEME}{req.run_id}/{block_name}/{k}",
            schema_version="skipped",
            sources=sources,
        )
        for k in sorted(produces)
    ]
    return BlockResult(
        run_id=req.run_id,
        status="ok",
        outputs=outputs,
        flags=[Flag(code="SKIPPED", message=f"{block_name} skipped: {reason}", severity="info")],
        metrics={"skipped": reason},
    )
