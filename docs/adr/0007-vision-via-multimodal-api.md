# ADR-0007: Vision, OCR and symbol reading through a multimodal LLM API

| | |
|---|---|
| Status | **Accepted** 2026-11-24, from the project owner's answer to OD-38: "we will be using Multimodal LLm using api" |
| Date | 2026-11-24 |
| Phase | Decided in Phase 0; built in Phase 2 (block 1) and used in Phases 3 and 6 |

## Context

For scans and the non-geometric parts of drawings, the plan's block 1 stack uses local models (plan §4.2 block 1, Phase 2):

- OCR: PaddleOCR or docTR.
- Symbol detection: RT-DETR or D-FINE through Hugging Face Transformers, "fine-tuned on dimension arrows, GD&T frames and symbols" (Phase 2 "Approach by input", task 4).
- Title blocks, notes and GD&T: Qwen2.5-VL / Qwen3-VL or Florence-2.

Earlier owner decisions: hosted model APIs only, no fine-tuning, no local LLM (OD-5, [ADR-0005](0005-model-hosting.md)); the provider is OpenAI (OD-37). OD-38 asked whether this also rules out the local non-LLM models above.

## Decision

OCR, symbol and GD&T recognition, and reading title blocks and notes on scans and images go to a **multimodal LLM over the OpenAI API**, through the Model Gateway (LiteLLM proxy, plan §4.1).

Unchanged, because they are deterministic and not models (plan principle 2, "Deterministic first, LLM second"):

- Vector inputs are parsed with geometry libraries: ezdxf for DXF, pdfplumber / pypdfium2 for vector PDF, OCP for STEP, trimesh for STL (plan Phase 2).
- Image pre-processing with OpenCV and scikit-image (deskew, denoise, line and circle detection) for scans (plan Phase 2).
- Every LLM output is validated by code: schema, geometry check (plan principle 2).

Dropped from the plan's block 1 stack: PaddleOCR, docTR, RT-DETR, D-FINE, Qwen-VL, Florence-2, and **Phase 2 task 4** (fine-tuning the symbol detector).

## Consequences

- The Phase 2 exit criteria do not change (dimension F1, title-block accuracy, locators, ECE; plan Phase 2). The multimodal model must meet them on the golden set.
- **Source locators** (principle 1): the model must return regions (bounding boxes) for what it reads, so each value gets a `SourceLocator.bbox`. If it cannot, the value is flagged `LOW_CONFIDENCE` (plan principle 3).
- **Calibration** (Phase 2 task 5) still applies. Confidence has to come from the model output or from agreement checks and then be calibrated. How is TBD in Phase 2.
- **Prompt injection** through drawing text (plan §10 risk 7) matters more, because images go straight to a model. Gateway guardrails apply, and extracted text is treated as data (plan §10).
- **Client data**: sending a client's scan to OpenAI needs that client's permission (OD-39, plan principle 7).
- No GPU is needed for block 1 (OD-20).
- Embeddings for the Knowledge Graph (bge-m3 / nomic-embed, plan Phase 3) are not covered by this answer (OD-42).

## Open items

- OD-39: client data and external APIs. Open.
- OD-42: embeddings through the API or locally. Open.
- OD-43: which OpenAI models. Open.

## Sources

- Plan §2.3 (principles 1 to 3, 7), §4.1, §4.2 block 1, §6 Phase 2 (approach, tasks 4 and 5, exit criteria), Phase 3, §10 risk 7.
- [open-decisions.md](../open-decisions.md): OD-5, OD-20, OD-37, OD-38, OD-39, OD-42, OD-43.
