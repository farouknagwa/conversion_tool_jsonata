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

## Workflow Mode (Step4_OUTPUT → Step5_OUTPUT)
Use `workflow_main.py` when your dataset is already in the Step4 pipeline folder structure:

- Target JSON edited in place: `Step4_OUTPUT/<QuestionId>/Updated/<QuestionId>.json`
- Input sheet: `Step4_OUTPUT/questions_updated_sheet.csv`

What it does:
- Empties `Step5_OUTPUT`
- Copies all contents from `Step4_OUTPUT` → `Step5_OUTPUT` (**excluding `*.log` files**)
- Rewrites `Step5_OUTPUT/questions_updated_sheet.csv` to **one row per `QuestionId`** keeping only:
  `QuestionId, SectionCode, language_iso_code, subject_id, subject_name, grade_id, grade_url_text, country_iso_code, parent_id, clone_parent_id, IsSuccess`
  and adds workflow output columns:
  `Error Message, Error Type, Warning Message, tex_cleaning`
- Cleans tex files (if `tex/<question_id>.figures/` exists):
  * Matches `<12-digit ID>.1.<index>.tex` → renames to `<question_id>.<indexmodified>.tex` (zero-padded)
  * Matches `<12-digit ID>.1.tex` → renames to `<question_id>.01.tex`
  * Copies renamed files to `Updated/` folder and removes `tex/` folder
- Runs HTML cleaning (`SIDE_TOOLS/jsons_htmltags_cleaning/clean_json_html.py`) **before** conversion for each processed question
- Converts JSONs **in place** inside `Step5_OUTPUT/<QuestionId>/Updated/<QuestionId>.json`
- Writes a Step5 log file in `Step5_OUTPUT`:
  `Step5_JsonCleaningAndConversion_<YYYYMMDD>_<HHMMSSmmm>.log`

Important:
- **IsSuccess gating**: Only rows where `IsSuccess=True` (from the input Step4 sheet) are processed in Step5.
  Rows with `IsSuccess=False` are skipped and their JSONs remain unchanged in `Step5_OUTPUT`.
- Paths are intentionally kept **relative** by default; run from the repo root or pass explicit paths.

Examples:

```bash
python3 -B workflow_main.py
python3 -B workflow_main.py --inputstep Step4_OUTPUT --outputstep Step5_OUTPUT
python3 -B workflow_main.py --inputstep path/to/Step4_OUTPUT --outputstep path/to/Step5_OUTPUT -v
```

## Supported Question Types
`mcq`, `mrq`, `gmrq`, `frq`, `frq_ai`, `oq`, `gapText`, `string`, `opinion`, `matching`, `counting`, `puzzle`, `input_box`

## Validation System
- **ERRORS**: Block conversion, file segregated to failure folder
- **WARNINGS**: Non-blocking issues, conversion proceeds normally
  - Tracked in separate Excel "Warnings" sheet
  - Examples: multipart without statement, single-part answer HTML structure issues, EG MCQ/MRQ with > 4 choices
- **AUTOMATIC FIXES**: Some warnings trigger automatic fixes during conversion
  - EG MCQ/MRQ with > 4 choices: extra distractors automatically removed, choices renumbered

## Conversion Rules
Type-specific JSONata rules live in `JSONATA_RULES/` (one `.jsonata` file per question type).

## Documentation
- See `SUMMARY.txt` for executive summary
- See `Usage.txt` for detailed usage instructions
- See `pre-conversion-validations.txt` for input validation rules
- See `post-conversion-validations.txt` for output validation rules
- See individual type structure files (e.g., `mcq.txt`, `mrq.txt`) for detailed JSON structure documentation
