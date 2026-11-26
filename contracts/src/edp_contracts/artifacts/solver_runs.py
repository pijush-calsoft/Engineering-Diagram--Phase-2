"""``solver_runs`` artifact, schema v0.1 (added 2026-11-26, additive: contract stays v0.1).

The Run Store record of block 6 (plan §2.2 and §4.1 name the Run Store; deck slide 40 "Run
Store: results, margins ... versioned and read only"). Block 8 reads every number it reports
from here or from ``margins``; nothing is typed into a report by hand or by a model (plan
Phase 6 Insight task 2).

One ``SolverRun`` per load case run: the solver, the material card row, the mesh and its
quality, the boundary conditions, the peak results and the modelling assumptions.
"""

from pydantic import BaseModel

from edp_contracts.block import SourceLocator

SCHEMA_VERSION = "0.1.0"


class MaterialUsed(BaseModel):
    grade: str
    fy_MPa: float
    gamma_M0: float
    E_MPa: float
    nu: float
    row: SourceLocator  # row in the domain pack's material file


class MeshInfo(BaseModel):
    elements: int
    nodes: int
    element_type: str
    size_max_mm: float
    size_min_mm: float
    min_scaled_jacobian: float | None = None
    mean_scaled_jacobian: float | None = None


class SolverRun(BaseModel):
    solver_run_id: str
    solver: str
    solver_version: str | None = None
    load_case_id: str
    load_case_row: SourceLocator
    illustrative_load: bool = False
    model_version: str
    material: MaterialUsed
    total_force_N: float
    fixed_nodes: int
    loaded_nodes: int
    max_von_mises_MPa: float
    max_point_mm: tuple[float, float, float]
    max_displacement_mm: float
    allowable_MPa: float
    seconds: float
    assumptions: list[str] = []


class SolverRuns(BaseModel):
    schema_version: str = SCHEMA_VERSION
    domain_pack: str
    materials_sha256: str
    load_cases_sha256: str
    mesh: MeshInfo
    runs: list[SolverRun] = []
