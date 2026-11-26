import math

import pytest

from edp_b6_solvers import calculix, packs
from edp_b6_solvers.block import mesh_sizes

TOOLS = calculix.ccx_path() is not None and calculix.gmsh_python() is not None
needs_tools = pytest.mark.skipif(not TOOLS, reason="CalculiX or Gmsh not installed (setup guide)")


def test_von_mises_of_uniaxial_and_pure_shear():
    assert calculix.von_mises([100.0, 0, 0, 0, 0, 0]) == pytest.approx(100.0)
    assert calculix.von_mises([0, 0, 0, 50.0, 0, 0]) == pytest.approx(50.0 * math.sqrt(3))


def test_parse_dat_reads_displacements_and_stresses():
    dat = """
 displacements (vx,vy,vz) for set NALL and time  0.1000000E+01

         1  1.000000E-03  0.000000E+00  0.000000E+00
         2  3.000000E-03  4.000000E-03  0.000000E+00

 stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set EALL and time  0.1000000E+01

         7   1  1.000000E+02  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00
         7   2  2.000000E+02  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00  0.000000E+00
"""
    disp, stress = calculix.parse_dat(dat)
    assert disp[2] == pytest.approx(5e-3) and stress[7] == pytest.approx(200.0)


def test_material_card_picks_the_yield_for_the_thickness():
    pack = packs.load("construction", "materials.json")
    thin, thick = packs.material(pack, "S355JR", 15.0), packs.material(pack, "s355jr", 25.0)
    assert (thin.fy, thick.fy) == (355.0, 345.0)  # EN 10025-2: t <= 16 and 16 < t <= 40
    assert thin.row.file_id == pack.sha256 and thin.row.handle == "S355JR@t<=16"
    with pytest.raises(packs.PackError):
        packs.material(pack, "S235JR", 10.0)


def test_mesh_size_follows_thickness_and_holes():
    assert mesh_sizes(15.0, [30.0, 30.0]) == (7.5, 1.875)
    assert mesh_sizes(40.0, [18.0]) == (9.0, 2.25)


@needs_tools
def test_cantilever_benchmark_within_three_percent(tmp_path):
    """Connector benchmark gate (plan Phase 5 exit criterion: within 3 % of reference).

    A 200 x 20 x 20 mm steel cantilever, fixed at x = 0, 1 kN down at the free end. Reference
    tip deflection from Timoshenko beam theory: F L^3 / (3 E I) + F L / (k G A), k = 5/6.
    """
    import cadquery as cq

    L, b, E, nu, F = 200.0, 20.0, 210000.0, 0.3, 1000.0
    step = tmp_path / "bar.step"
    cq.exporters.export(cq.Workplane("XY").box(L, b, b, centered=False), str(step))
    mesh = calculix.mesh_step(step, 4.0, 2.0, timeout=300)
    fixed = [n for n, p in mesh.nodes.items() if abs(p[0]) < 1e-6]
    tip = [n for n, p in mesh.nodes.items() if abs(p[0] - L) < 1e-6]
    loads = {n: (0.0, 0.0, -F / len(tip)) for n in tip}
    result = calculix.run_ccx(calculix.write_inp(mesh, E, nu, fixed, loads), mesh, timeout=600)
    inertia, area, shear = b**4 / 12, b * b, E / (2 * (1 + nu))
    reference = F * L**3 / (3 * E * inertia) + F * L / (5 / 6 * shear * area)
    assert result.max_displacement == pytest.approx(reference, rel=0.03)
