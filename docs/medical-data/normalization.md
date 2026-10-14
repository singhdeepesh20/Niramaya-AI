# Deterministic normalization

The parser preserves the reported value and unit. It creates a `normalized_value` only for an explicit conversion rule and recognized source unit:

| Finding | Source unit | Normalized unit | Rule |
|---|---|---|---|
| Hemoglobin | g/L | g/dL | multiply by 0.1 |
| Glucose | mmol/L | mg/dL | multiply by 18.0182 |
| Total/HDL/LDL/VLDL cholesterol | mmol/L | mg/dL | multiply by 38.67 |
| Triglycerides | mmol/L | mg/dL | multiply by 88.57 |

Unrecognized labels or units remain unnormalized. Conversions are deterministic formatting helpers, not clinical interpretation. Reference ranges are retained as source text; the parser does not convert range units or infer a normal/abnormal result. Rule updates must be versioned and covered by synthetic tests.
