# JSON Question Conversion Tool (JSONata)

Automated tool to convert educational question JSON files from a legacy structure to a new standardized structure, with comprehensive validation and error reporting.

## Features
- Converts 12 question types: MCQ, MRQ, GMRQ, FRQ, Ordering, Gap-Text, String, Opinion, Matching, Counting, Puzzle, Input-Box
- Three-stage pipeline: Pre-validation → Conversion → Post-validation
- Uses JSONata transformation rules for type-specific conversions
- Batch processing with progress tracking and error recovery
- Generates detailed error reports with separate warnings tracking (Excel + text logs)
- BeautifulSoup-based HTML validation for answer explanations
- Part-specific explanation extraction for multipart questions

## Pipeline
1. Pre-conversion validation (checks OLD structure)
2. Conversion (JSONata rules per type)
3. Post-conversion validation (ensures NEW structure)

## Outputs
- `OUTPUTS/CONVERTED/` — Successfully converted files
- `OUTPUTS/PRE_CONVERSION_VALIDATION_FAILED/` — Invalid input structure (blocking errors only)
- `OUTPUTS/CONVERSION_FAILED/` — Transformation errors
- `OUTPUTS/POST_CONVERSION_VALIDATION_FAILED/` — Invalid output structure
- `OUTPUTS/LOGS_REPORTS/` — Error reports (.xlsx with Errors + Warnings sheets, .log)

## Requirements
Install dependencies:

```bash
pip install -r requirements.txt
```
Requires: `jsonata-python`, `tqdm`, `openpyxl`, `beautifulsoup4`.

## Quick Start
Process all files in `INPUT/` with progress:

```bash
python3 -B main.py
```

Verbose mode:

```bash
python3 -B main.py -v
```

Specify paths:

```bash
python3 -B main.py --input path/to/files --output path/to/output
```

Filter by types:

```bash
python3 -B main.py --types mcq,mrq,counting
```

Dry-run (validation only):

```bash
python3 -B main.py --dry-run
```

## Supported Question Types
`mcq`, `mrq`, `gmrq`, `frq`, `frq_ai`, `oq`, `gapText`, `string`, `opinion`, `matching`, `counting`, `puzzle`, `input_box`

## Validation System
- **ERRORS**: Block conversion, file segregated to failure folder
- **WARNINGS**: Non-blocking issues, conversion proceeds normally
  - Tracked in separate Excel "Warnings" sheet
  - Examples: multipart without statement, single-part answer HTML structure issues

## Conversion Rules
Type-specific JSONata rules live in `JSONATA_RULES/` (one `.jsonata` file per question type).

## Documentation
- See `SUMMARY.txt` for executive summary
- See `Usage.txt` for detailed usage instructions
- See `pre-conversion-validations.txt` for input validation rules
- See `post-conversion-validations.txt` for output validation rules
- See individual type structure files (e.g., `mcq.txt`, `mrq.txt`) for detailed JSON structure documentation
