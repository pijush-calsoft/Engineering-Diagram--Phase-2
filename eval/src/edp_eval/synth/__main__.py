"""CLI for the synthetic golden-set generator (OD-7)."""

import argparse
from pathlib import Path

from edp_eval.synth import write_set

parser = argparse.ArgumentParser(prog="python -m edp_eval.synth", description=__doc__)
parser.add_argument("--out", type=Path, required=True, help="output folder (keep it under eval/golden/data/)")
parser.add_argument("--count", type=int, required=True, help="number of drawings")
parser.add_argument("--seed", type=int, required=True, help="seed; same seed and count give the same set")
parser.add_argument("--uri-prefix", required=True, help="Data Fabric location for the manifest, s3://...")
args = parser.parse_args()

manifest = write_set(args.out, args.count, args.seed, args.uri_prefix)
check = manifest.phase0_exit_check()
print(f"Wrote {len(manifest.items)} drawings, labels and manifest.json to {args.out}")
print(f"Phase 0 exit check: {check.labelled_drawings} labelled drawings, passed={check.passed}")
