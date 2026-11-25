"""Gateway command line.

``python -m edp_gateway check``  one short call per configured role and one embedding, on
                                 synthetic text only; prints models, tokens and cost, never the key.
``python -m edp_gateway usage``  totals from the usage log, by service, kind, model and status.
"""

import argparse
import json

from pydantic import BaseModel

from edp_gateway import CompletionRequest, Gateway, GatewayConfig, GatewayError


class _Ping(BaseModel):
    word: str


def check(gw: Gateway) -> int:
    print(
        f"key set: {bool(gw.config.api_key)} | provider: {gw.config.provider} | "
        f"budget: {gw.config.budget_usd if gw.config.budget_usd is not None else 'none (OD-50)'}"
    )
    failures = 0
    for role, model in sorted(gw.config.models.items()):
        req = CompletionRequest(
            service="gateway-check",
            role=role,  # type: ignore[arg-type]
            prompt_version="check-1",
            data_class="synthetic",
            instructions='Reply as JSON with the field "word" set to "ready".',
        )
        try:
            res = gw.complete(req, output_model=_Ping)
            u = res.usage
            print(
                f"{role:7} {model}: ok, reply={res.parsed.word!r}, "
                f"tokens={u.input_tokens}+{u.output_tokens}, cost_usd={u.cost_usd}"
            )
        except GatewayError as e:
            failures += 1
            print(f"{role:7} {model}: FAILED {e}")
        except Exception as e:  # noqa: BLE001 - report every provider error, keep checking
            failures += 1
            print(f"{role:7} {model}: FAILED {type(e).__name__}")
    try:
        emb = gw.embed("gateway-check", ["hole diameter 6 mm"], data_class="synthetic")
        print(
            f"embed   {gw.config.embedding_model}: ok, dimensions={len(emb.vectors[0])}, "
            f"tokens={emb.usage.input_tokens}, cost_usd={emb.usage.cost_usd}"
        )
    except Exception as e:  # noqa: BLE001
        failures += 1
        print(f"embed   {gw.config.embedding_model}: FAILED {type(e).__name__}")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m edp_gateway", description=__doc__)
    ap.add_argument("command", choices=["check", "usage"])
    args = ap.parse_args()
    gw = Gateway(GatewayConfig.load())
    if args.command == "check":
        return check(gw)
    print(json.dumps({"spent_usd": gw.usage.spent_usd(), "by_group": gw.usage.summary()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
