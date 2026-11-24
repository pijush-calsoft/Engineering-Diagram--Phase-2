import pytest
from pydantic import ValidationError

from edp_contracts import (
    Artifact,
    Block,
    BlockContract,
    BlockRequest,
    BlockResult,
    Flag,
    SourceLocator,
)
from edp_contracts.events import ALL_SUBJECTS
from edp_contracts.registry import discover_blocks


def loc(**kw) -> SourceLocator:
    return SourceLocator(**{"file_id": "f1", "version": "c1", "confidence": 0.9, **kw})


class EchoBlock:
    name = "echo"
    version = "0.0.1"
    accepts = {"geometry"}
    produces = {"geometry"}

    def run(self, req: BlockRequest) -> BlockResult:
        return BlockResult(run_id=req.run_id, status="ok", outputs=req.inputs)


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_must_be_in_unit_interval(confidence):
    with pytest.raises(ValidationError):
        loc(confidence=confidence)


def test_confidence_is_required():
    with pytest.raises(ValidationError):
        SourceLocator(file_id="f1", version="c1")


def test_flag_severity_defaults_to_review_and_is_restricted():
    assert Flag(code="LOW_CONFIDENCE", message="m").severity == "review"
    with pytest.raises(ValidationError):
        Flag(code="X", message="m", severity="warning")


def test_result_status_is_restricted():
    with pytest.raises(ValidationError):
        BlockResult(run_id="r", status="done", outputs=[])


def test_mutable_defaults_are_not_shared():
    a = Artifact(kind="geometry", uri="s3://a", schema_version="0.1.0")
    b = Artifact(kind="geometry", uri="s3://b", schema_version="0.1.0")
    a.sources.append(loc())
    assert b.sources == []


def test_block_protocol_and_contract_body():
    block = EchoBlock()
    assert isinstance(block, Block)
    art = Artifact(kind="geometry", uri="s3://x", schema_version="0.1.0", sources=[loc(handle="1A")])
    result = block.run(BlockRequest(run_id="r1", inputs=[art]))
    assert result.status == "ok" and result.outputs[0].sources[0].handle == "1A"

    body = BlockContract.of(block, {"geometry": "0.1.0"})
    assert body.contract_version == "0.1.0"
    assert body.accepts == ["geometry"] and body.produces == ["geometry"]


def test_request_round_trips_through_json():
    step = Artifact(kind="step", uri="s3://m.step", schema_version="ap242", sources=[loc(bbox=(0, 0, 1, 1))])
    req = BlockRequest(run_id="r1", inputs=[step], params={"units": "mm"})
    assert BlockRequest.model_validate_json(req.model_dump_json()) == req


def test_discover_blocks_returns_dict_when_nothing_registered():
    assert isinstance(discover_blocks(), dict)


def test_event_subjects_are_unique():
    assert len(ALL_SUBJECTS) == len(set(ALL_SUBJECTS))
