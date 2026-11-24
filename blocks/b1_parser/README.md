# Block 1: Drawing Parser

**Status: not started.** Planned for Phase 2.

Extract geometry, dimensions, the title block and source locators from every R1 input type. Output: `geometry` artifact.

## Planned stack

| Input | Method | Source |
|---|---|---|
| DXF | ezdxf | plan Phase 2 |
| DWG | LibreDWG `dwg2dxf` as an isolated CLI (GPLv3), then the DXF path | plan Phase 2, §9 |
| Vector PDF | pdfplumber / pypdfium2 | plan Phase 2 |
| STEP, IGES | OCP / pythonocc-core | plan Phase 2 |
| STL | trimesh | plan Phase 2 |
| Scans: pre-processing | OpenCV + scikit-image (deskew, denoise, line and circle detection) | plan Phase 2 |
| Scans and images: OCR, symbols, GD&T, title blocks, notes | **Multimodal LLM through the OpenAI API**, via the Model Gateway | [ADR-0007](../../docs/adr/0007-vision-via-multimodal-api.md) (OD-38), replacing plan §4.2's PaddleOCR / docTR, RT-DETR / D-FINE and Qwen-VL / Florence-2 |

Phase 2 task 4 (fine-tune the symbol detector) is dropped by OD-5 and OD-38. The exit criteria stay as in plan Phase 2. The synthetic golden set in `eval/` is the first test data.
