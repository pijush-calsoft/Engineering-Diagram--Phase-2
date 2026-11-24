# Golden dataset: public data sources (research for OD-7)

| | |
|---|---|
| Purpose | Find openly licensed drawings and 3D models for the golden set (plan Phase 0 task 2: "Use only internal or openly licensed drawings") |
| Method | Web research, 2026-11-24. Licence text was quoted from each source page. Nothing has been downloaded |
| Status | **Research only.** Before any file is ingested, the accountable owner records its licence, attribution and provenance, and legal confirms the licence (plan §4 preamble, §9) |

## Result in one line

The search found **no public dataset with 60 to 100 commercially licensed 2D drawings that carry dimension ground truth**. Most of the golden set has to be internal. The synthetic generator (`edp_eval.synth`, see [eval/README.md](../../eval/README.md)) covers this.

## A. Candidates where commercial use appears allowed

| Source | Contents | Licence as stated on the page | Caveats |
|---|---|---|---|
| NIST MBE PMI test cases (nist.gov, "MBE PMI validation and conformance testing") | About 11 test cases (CTC 01 to 05, FTC 06 to 11, plus STC, HTC, MTC). 2D drawings of annotated 3D models, STEP AP242/AP203 with semantic PMI, native CAD | "The test cases, CAD models, and STEP files can be used without any restrictions." | Acknowledgement requested; no NIST logo in promotion; "may be subject to foreign copyright". The drawing file format was not confirmed. **Best public source for 3D models with GD&T ground truth** |
| HABS/HAER/HALS measured drawings (US National Park Service, Library of Congress) | Scanned measured drawings with title blocks; civil and industrial-heritage subjects | "Materials created for HABS, HAER, or HALS are in the public domain." | The Library of Congress rights page could not be opened. Items copied from other sources may be restricted, so check each item. Not machined parts. Useful for the **scan** slice |
| FreeCAD-library (GitHub) | Standard and mechanical parts as STEP, FCStd, some STL | "All Parts in this repository are licensed under CC-BY 3.0" | Attribution required. Per-part provenance not documented |
| CERN SY-RF MKS open hardware | PDF manufacturing drawings for 9 RF components | CERN OHL v1.2 | Read the full OHL v1.2 terms before redistribution. Useful for the **vector PDF** slice |
| engineering-drawings-as1100 (Hugging Face) | 5 parts, JPG, title blocks, labelled title-block faults | "cc-by-4.0" | Very small; base-drawing origin not stated. Title-block checks only |
| KiCad packages3D | STEP models of electronic components | CC BY-SA 4.0 | Share-alike; little mechanical relevance |

## B. Research baselines only (not for the golden set)

| Source | Why excluded |
|---|---|
| Fusion 360 Gallery | "only for non-commercial research purposes" (plan §9 watch-list) |
| TechMB (Hugging Face) | Built from Fusion 360 Gallery parts; inherits the non-commercial terms |
| ABC dataset | Copyright stays with creators under Onshape terms; some pre-2018 documents may reserve rights. Needs legal review (plan §9) |
| DeepCAD, Drawing2CAD / CAD-VGDrawing | Derived from ABC / Onshape; inherit those terms |

## C. Not verified

Roboflow Universe engineering-drawing sets (pages blocked; a search snippet said CC BY 4.0, origin unknown), Zenodo record 16876577 (CC BY 4.0, restricted access), Thingi10K (per-item licences; meshes), MCB, eDOCr sample drawings, NASA-3D-Resources, GrabCAD. None of these should be used until its licence is read on the source page.

## Proposed use

| Golden-set slice (plan Phase 0 task 2) | Source |
|---|---|
| Vector DXF drawings (60 to 100) | Synthetic generator, ISO and ASME profiles, exact labels |
| Vector PDF and scans | Rendered from the synthetic DXF (next step), plus CERN OHL PDFs and HAER scans labelled in-house, after licence sign-off |
| 20 STEP/STL models | NIST MBE PMI test cases first, then FreeCAD-library parts (CC-BY 3.0, with attribution), after licence sign-off |
