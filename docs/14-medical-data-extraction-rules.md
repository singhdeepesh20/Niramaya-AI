# Medical-data extraction rules

Implementation: `app/documents/extraction.py`. Processing is deterministic regex/rule logic over extracted text; it does not call an LLM or infer diagnoses.

## Classification

`classify_document` counts explicit indicators for CBC, lipid/liver/kidney/thyroid/glucose/urinalysis, MRI/CT/X-ray/ultrasound/ECG, prescription and discharge-summary categories. A configured minimum count must match. The best score selects a type; tied top matches become `unknown`/ambiguous. A weaker known-lab signal can return broad `general_lab`. Scores and matched indicators are explainability metadata, not clinical confidence.

## Laboratory values and metadata

`TEST_ALIASES` maps explicit strings to canonical identifiers, including blood count, lipids, liver/kidney, glucose, thyroid and urinalysis fields. The parser accepts a line beginning with a recognized alias followed by a separator and a numeric or enumerated qualitative value. It separately captures nearby reference-range syntax and explicit high/low/abnormal flags. It preserves source value, unit, alias, page and excerpt. It does not estimate a missing unit, convert ranges, or infer abnormality from a population interval.

`_META_ALIASES` recognizes report labels such as patient name/ID, age, sex, report/collection date, physician, report ID and laboratory. These are sensitive extracted fields; retention, UI display and access should follow the same protections as medical findings.

## Normalization

Only explicit conversions are applied: hemoglobin g/L→g/dL (0.1); glucose mmol/L→mg/dL (18.0182); total/HDL/LDL/VLDL cholesterol mmol/L→mg/dL (38.67); triglycerides mmol/L→mg/dL (88.57). Original and normalized values are both retained. Unknown units remain unnormalized. See [normalization table](medical-data/normalization.md).

## Review conditions and limitations

Review is required when classification is unknown/ambiguous, OCR cannot recover scan-only text, per-page lab values conflict, extraction is ambiguous, or no supported structured result is found for a non-imaging/non-prescription document. Explicit rule catalogue coverage is not comprehensive; section extraction handles selected headings (examination, modality, indication, technique, findings, impression, diagnosis and follow-up). Parser tests in `tests/test_document_extraction.py` and `tests/test_image_document_processing.py` use synthetic content. OCR availability and clinical accuracy are not established by those tests.
