"""CLI for the synthetic golden-set generator (OD-7).

Plain set:  --count N
Family set for the Knowledge Graph evaluation:  --families N --revisions R
DWG copies of an existing set (needs LibreDWG):  --dwg-from DIR
Vector-PDF copies of an existing set:  --pdf-from DIR
Scan copies of a vector-PDF set:  --scan-from DIR --dpi D --max-skew-deg A --seed S
3D models (STEP and STL):  --models N
"""

import argparse
from pathlib import Path

from edp_b1_parser.dwg import converter
from edp_eval.synth import write_family_set, write_set
from edp_eval.synth.dwg import dxf2dwg_path, write_dwg_set
from edp_eval.synth.models import write_model_set
from edp_eval.synth.pdf import write_pdf_set
from edp_eval.synth.scan import write_scan_set

parser = argparse.ArgumentParser(prog="python -m edp_eval.synth", description=__doc__)
parser.add_argument("--out", type=Path, required=True, help="output folder (keep it under eval/golden/data/)")
mode = parser.add_mutually_exclusive_group(required=True)
mode.add_argument("--count", type=int, help="number of drawings in a plain set")
mode.add_argument("--families", type=int, help="number of part families (Knowledge Graph set)")
mode.add_argument("--dwg-from", type=Path, help="convert this DXF set to DWG (needs LibreDWG dxf2dwg)")
mode.add_argument("--pdf-from", type=Path, help="write vector-PDF copies of this DXF set")
mode.add_argument("--models", type=int, help="number of 3D models (STEP and STL)")
mode.add_argument("--scan-from", type=Path, help="render this vector-PDF set as degraded scans (PNG)")
parser.add_argument("--dpi", type=float, help="scan resolution (with --scan-from)")
parser.add_argument("--max-skew-deg", type=float, help="largest random rotation (with --scan-from)")
parser.add_argument("--revisions", type=int, default=None, help="revisions per family (with --families)")
parser.add_argument("--seed", type=int, help="seed; same arguments give the same set")
parser.add_argument("--uri-prefix", help="Data Fabric location for the manifest, s3://...")
args = parser.parse_args()

if args.dwg_from is not None:
    exe = converter()
    if exe is None:
        parser.error("LibreDWG not found: set EDP_DWG2DXF to the dwg2dxf executable")
    ids = write_dwg_set(args.dwg_from, args.out, dxf2dwg_path(exe))
    print(f"Wrote {len(ids)} DWG drawings and labels to {args.out}")
    raise SystemExit(0)
if args.pdf_from is not None:
    ids = write_pdf_set(args.pdf_from, args.out)
    print(f"Wrote {len(ids)} vector PDFs, page maps and labels to {args.out}")
    raise SystemExit(0)
if args.scan_from is not None:
    if args.dpi is None or args.max_skew_deg is None or args.seed is None:
        parser.error("--scan-from needs --dpi, --max-skew-deg and --seed")
    ids = write_scan_set(args.scan_from, args.out, args.dpi, args.max_skew_deg, args.seed)
    print(f"Wrote {len(ids)} scans, scan maps and labels to {args.out}")
    raise SystemExit(0)
if args.seed is None or args.uri_prefix is None:
    parser.error("--seed and --uri-prefix are required for --count and --families")

if args.models is not None:
    manifest = write_model_set(args.out, args.models, args.seed, args.uri_prefix)
elif args.families is not None:
    if args.revisions is None:
        parser.error("--families needs --revisions")
    manifest = write_family_set(args.out, args.families, args.revisions, args.seed, args.uri_prefix)
else:
    manifest = write_set(args.out, args.count, args.seed, args.uri_prefix)
check = manifest.phase0_exit_check()
print(f"Wrote {len(manifest.items)} drawings, labels and manifest.json to {args.out}")
print(f"Phase 0 exit check: {check.labelled_drawings} labelled drawings, passed={check.passed}")
