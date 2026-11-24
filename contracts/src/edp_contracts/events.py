"""Event subjects (plan section 3 and Appendix B)."""

FABRIC_FILE_INGESTED = "fabric.file.ingested"
FABRIC_DATASET_VERSIONED = "fabric.dataset.versioned"
FABRIC_DATASET_PROMOTED = "fabric.dataset.promoted"

RUN_PLANNED = "run.planned"
RUN_BLOCK_STARTED = "run.block.started"
RUN_BLOCK_COMPLETED = "run.block.completed"
RUN_BLOCK_FAILED = "run.block.failed"

CATALOGUE_LINEAGE_RECORDED = "catalogue.lineage.recorded"

REVIEW_REQUESTED = "review.requested"
REVIEW_RESOLVED = "review.resolved"

TWIN_STATE_UPDATED = "twin.state.updated"
TWIN_ALERT_RAISED = "twin.alert.raised"

ALL_SUBJECTS = (
    FABRIC_FILE_INGESTED,
    FABRIC_DATASET_VERSIONED,
    FABRIC_DATASET_PROMOTED,
    RUN_PLANNED,
    RUN_BLOCK_STARTED,
    RUN_BLOCK_COMPLETED,
    RUN_BLOCK_FAILED,
    CATALOGUE_LINEAGE_RECORDED,
    REVIEW_REQUESTED,
    REVIEW_RESOLVED,
    TWIN_STATE_UPDATED,
    TWIN_ALERT_RAISED,
)
