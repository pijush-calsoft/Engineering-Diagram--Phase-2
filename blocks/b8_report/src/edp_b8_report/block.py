"""Block 8, Insight and report, as a plug-in (plan §3, Phase 6): Run Store records in,
``report`` (JSON) and its DOCX out.

1. Builds the Run Store for the run: ``margins`` and ``solver_runs`` from block 6, the design
   graph, the title block, and the domain-pack files the solver used. A pack file whose hash
   differs from the one recorded by the solver run blocks the report (``PACK_CHANGED``).
2. Composes the descriptive and diagnostic report from templates (``compose``).
3. Fact-checks it (``factcheck``). Any problem blocks release: no DOCX is written and the run
   stops for a person (plan Phase 6 Insight task 3; deck slide 40).
4. Otherwise writes the DOCX and asks for engineer sign-off: the run pauses at review, and
   approving it is the sign-off (deck slide 77 "Signed copies are locked"; OD-40 open on wording).
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from edp_b8_report.compose import compose
from edp_b8_report.docx_writer import to_docx
from edp_b8_report.factcheck import RunStore, check
from edp_contracts import Artifact, BlockRequest, BlockResult, Flag
from edp_contracts.artifacts.report import SCHEMA_VERSION
from edp_kit import ArtifactStore, pass_through, skip_reason

REPO_PACKS = Path(__file__).resolve().parents[4] / "domain_packs"


def _packs_root() -> Path:
    env = os.environ.get("EDP_DOMAIN_PACKS", "").strip()
    return Path(env) if env else REPO_PACKS


class InsightReport:
    name = "b8_report"
    version = "0.1.0"
    accepts = {"margins", "solver_runs", "design_graph", "geometry"}
    produces = {"report", "docx"}

    def __init__(self, store: ArtifactStore | None = None) -> None:
        self._store = store

    @property
    def store(self) -> ArtifactStore:
        if self._store is None:
            from edp_fabric import FabricStore  # entry-point loading: local Fabric (ADR-0008)

            data_dir = os.environ.get("EDP_DATA_DIR")
            if not data_dir:
                raise RuntimeError(
                    "InsightReport needs a store, or EDP_DATA_DIR set to the local data folder"
                )
            self._store = FabricStore(Path(data_dir) / "fabric")
        return self._store

    def run(self, req: BlockRequest) -> BlockResult:
        reason = skip_reason(req)
        if reason:
            return pass_through(self.name, self.produces, req, reason)
        by_kind = {a.kind: a for a in req.inputs}
        missing = sorted({"margins", "solver_runs", "design_graph"} - set(by_kind))
        if missing:
            return self._blocked(req, "MISSING_INPUT", f"report needs {', '.join(missing)}")
        docs: dict[str, Any] = {
            kind: json.loads(self.store.read(by_kind[kind].uri))
            for kind in ("margins", "solver_runs", "design_graph")
        }
        if "geometry" in by_kind:
            docs["title_block"] = (
                json.loads(self.store.read(by_kind["geometry"].uri)).get("title_block") or {}
            )
        runs = docs["solver_runs"]
        for name, recorded in (
            ("load_cases", runs["load_cases_sha256"]),
            ("materials", runs["materials_sha256"]),
        ):
            path = _packs_root() / runs["domain_pack"] / f"{name}.json"
            raw = path.read_bytes() if path.is_file() else b""
            if hashlib.sha256(raw).hexdigest() != recorded:
                return self._blocked(
                    req,
                    "PACK_CHANGED",
                    f"{path.name} differs from the file the solver used (hash {recorded[:12]})",
                )
            docs[name] = json.loads(raw)
        store = RunStore(docs)
        report, identifiers, summary = compose(req.run_id, store)
        problems = check(report, store, identifiers)
        report_uri = self.store.write(req.run_id, self.name, "report.json", report.model_dump_json().encode())
        bad_claims = {p.split(":", 1)[0] for p in problems}
        metrics: dict[str, Any] = {
            "claims": len(report.claims),
            "claims_verified": sum(1 for c in report.claims if c.id not in bad_claims),
            "fact_check_problems": problems,
            "governing": summary["governing"],
        }
        outputs = [
            Artifact(
                kind="report",
                uri=report_uri,
                schema_version=SCHEMA_VERSION,
                sources=by_kind["margins"].sources,
            )
        ]
        if problems:
            # Blocking (AC-P6-03): the run stops here; a reviewer cannot approve past a failed check.
            flags = [Flag(code="FACT_CHECK_FAILED", message=p, severity="block") for p in problems]
            return BlockResult(
                run_id=req.run_id, status="failed", outputs=outputs, flags=flags, metrics=metrics
            )
        meta = {
            **summary,
            "domain_pack": runs["domain_pack"],
            "materials_sha256": runs["materials_sha256"],
            "load_cases_sha256": runs["load_cases_sha256"],
        }
        docx_uri = self.store.write(req.run_id, self.name, "report.docx", to_docx(report, meta))
        outputs.append(
            Artifact(kind="docx", uri=docx_uri, schema_version="file", sources=by_kind["margins"].sources)
        )
        metrics["docx_uri"] = docx_uri
        flags = [
            Flag(
                code="SIGN_OFF_REQUIRED",
                message="the report is a draft until an engineer approves it",
                severity="review",
            )
        ]
        return BlockResult(
            run_id=req.run_id, status="needs_review", outputs=outputs, flags=flags, metrics=metrics
        )

    def _blocked(self, req: BlockRequest, code: str, message: str) -> BlockResult:
        return BlockResult(
            run_id=req.run_id,
            status="failed",
            outputs=[],
            flags=[Flag(code=code, message=message, severity="block")],
        )
