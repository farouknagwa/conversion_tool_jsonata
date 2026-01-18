"""
Workflow orchestrator for JSON cleaning + conversion pipeline.

This is a Step4_OUTPUT -> Step5_OUTPUT workflow:
- Copy full Step4_OUTPUT folder contents into Step5_OUTPUT (excluding *.log files), after emptying Step5_OUTPUT.
- In Step5_OUTPUT, rewrite questions_updated_sheet.csv to a question-level sheet (one row per QuestionId)
  with the required metadata columns and conversion results columns.
- For each QuestionId, run HTML cleaning (using SIDE_TOOLS/jsons_htmltags_cleaning/clean_json_html.py)
  on Step5_OUTPUT/<QuestionId>/Updated/<QuestionId>.json, then run the conversion tool in-place.
- Write a Step5 log file in the Step5_OUTPUT root:
  Step5_JsonCleaningAndConversion_<date>_<timestamp>.log

Important: This script intentionally uses relative paths by default (no .resolve()).
Run it from the repo root, or pass explicit --inputstep/--outputstep paths.
"""

import argparse
import csv
import sys
import shutil
import importlib.util
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from SCRIPTS.config import ERROR_TYPES
from SCRIPTS.utils import load_json_file, save_json_file, ValidationError, ConversionError
from SCRIPTS.pre_validator import validate_pre_conversion
from SCRIPTS.converter import convert_question
from SCRIPTS.post_validator import validate_post_conversion


REQUIRED_SHEET_COLUMNS = [
    "QuestionId",
    "SectionCode",
    "language_iso_code",
    "subject_id",
    "subject_name",
    "grade_id",
    "grade_url_text",
    "country_iso_code",
    "parent_id",
    "clone_parent_id",
    "IsSuccess",
]

OUTPUT_SHEET_COLUMNS = REQUIRED_SHEET_COLUMNS + [
    "Error Message",
    "Error Type",
    "Warning Message",
    "tex_cleaning",
]


def _now_step_style_stamp() -> Tuple[str, str]:
    """
    Returns (date_YYYYMMDD, time_HHMMSSmmm) to match Step4 naming style.
    """
    now = datetime.now()
    date = now.strftime("%Y%m%d")
    time_hhmmss = now.strftime("%H%M%S")
    millis = f"{now.microsecond // 1000:03d}"
    return date, f"{time_hhmmss}{millis}"


class Logger:
    def __init__(self, log_path: Path, verbose: bool = False):
        self.log_path = log_path
        self.verbose = verbose
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write("")  # truncate

    def info(self, msg: str) -> None:
        line = msg.rstrip("\n")
        print(line)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def debug(self, msg: str) -> None:
        if self.verbose:
            self.info(msg)


def empty_directory(dir_path: Path) -> None:
    if not dir_path.exists():
        dir_path.mkdir(parents=True, exist_ok=True)
        return
    if not dir_path.is_dir():
        raise ValueError(f"Expected a directory path for Step5_OUTPUT, got: {dir_path}")
    for child in dir_path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def copy_step4_to_step5(step4_dir: Path, step5_dir: Path, logger: Logger) -> None:
    if not step4_dir.exists() or not step4_dir.is_dir():
        raise ValueError(f"Step4_OUTPUT folder not found or not a directory: {step4_dir}")

    def ignore_logs(_dir: str, names: List[str]) -> List[str]:
        return [name for name in names if name.lower().endswith(".log")]

    logger.info(f"Copying Step4 -> Step5 (excluding *.log): {step4_dir} -> {step5_dir}")
    shutil.copytree(step4_dir, step5_dir, dirs_exist_ok=True, ignore=ignore_logs)


def load_cleaner_module(cleaner_path: Path):
    """
    Load clean_json_html.py as a module.

    Path resolution rules:
    - If cleaner_path is absolute: use it as-is.
    - If cleaner_path is relative:
      1) Try relative to current working directory (where the command is run)
      2) If not found, try relative to this script's directory
    """
    original_path = cleaner_path
    tried_paths: List[Path] = []

    if cleaner_path.is_absolute():
        tried_paths.append(cleaner_path)
        resolved = cleaner_path
    else:
        cwd_candidate = Path.cwd() / cleaner_path
        tried_paths.append(cwd_candidate)
        if cwd_candidate.exists():
            resolved = cwd_candidate
        else:
            script_dir_candidate = Path(__file__).resolve().parent / cleaner_path
            tried_paths.append(script_dir_candidate)
            resolved = script_dir_candidate

    if not resolved.exists():
        tried = " | ".join(str(p) for p in tried_paths)
        raise FileNotFoundError(
            f"Cleaning script not found. Given: {original_path}. Tried: {tried}. "
            f"Pass a correct path or run from a directory that has SIDE_TOOLS/."
        )
    spec = importlib.util.spec_from_file_location("clean_json_html", resolved)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load module spec for: {resolved}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_tex_files(question_id: str, updated_dir: Path, logger: Logger) -> str:
    """
    Clean tex files from tex/<question_id>.figures/ folder.
    
    Finds files matching pattern: <12-digit ID>.1.<index>.tex in tex/<question_id>.figures/
    Renames them to <question_id>.<indexmodified>.tex (with leading zeros: 1→01, 2→02, but 10→10, 13→13)
    Copies renamed files to Updated/ folder
    Removes the entire tex/ folder
    
    Args:
        question_id: The question ID
        updated_dir: Path to Updated/ folder (step5_dir / qid / "Updated")
        logger: Logger instance
    
    Returns:
        Status message for logging (e.g., "Cleaned X files" or "No tex folder found" or error message)
    """
    tex_dir = updated_dir / "tex"
    
    if not tex_dir.exists() or not tex_dir.is_dir():
        return "No tex folder found"
    
    figures_dir = tex_dir / f"{question_id}.figures"
    
    if not figures_dir.exists() or not figures_dir.is_dir():
        # Remove tex folder if figures subfolder doesn't exist
        try:
            shutil.rmtree(tex_dir)
            return "tex folder removed (no figures subfolder)"
        except Exception as e:
            return f"Error removing tex folder: {str(e)}"
    
    # Pattern 1: <12-digit ID>.1.<index>.tex
    # Pattern 2: <12-digit ID>.1.tex (without index)
    pattern_with_index = re.compile(r"^(\d{12})\.1\.(\d+)\.tex$")
    pattern_without_index = re.compile(r"^(\d{12})\.1\.tex$")
    
    cleaned_count = 0
    errors = []
    
    try:
        # Find matching tex files
        matching_files = []
        for tex_file in figures_dir.glob("*.tex"):
            # Check pattern with index first
            match = pattern_with_index.match(tex_file.name)
            if match:
                # Group 1: 12-digit ID (ignored), Group 2: index
                index = int(match.group(2))
                # Format index with leading zeros (1→01, 2→02, but 10→10, 13→13)
                # So zero-pad to 2 digits
                indexmodified = f"{index:02d}"
                new_name = f"{question_id}.{indexmodified}.tex"
                matching_files.append((tex_file, new_name))
            else:
                # Check pattern without index
                match = pattern_without_index.match(tex_file.name)
                if match:
                    # Rename .1 to .01
                    new_name = f"{question_id}.01.tex"
                    matching_files.append((tex_file, new_name))
        
        if not matching_files:
            # No matching files, just remove tex folder
            shutil.rmtree(tex_dir)
            return "tex folder removed (no matching files)"
        
        # Copy renamed files to Updated/ folder
        for source_file, new_name in matching_files:
            try:
                dest_file = updated_dir / new_name
                shutil.copy2(source_file, dest_file)
                cleaned_count += 1
            except Exception as e:
                errors.append(f"Failed to copy {source_file.name}: {str(e)}")
        
        # Remove the entire tex folder
        shutil.rmtree(tex_dir)
        
        if errors:
            return f"Cleaned {cleaned_count} files, but errors: {'; '.join(errors)}"
        else:
            return f"Cleaned {cleaned_count} file(s)"
            
    except Exception as e:
        return f"Error during tex cleaning: {str(e)}"


def read_questions_sheet(sheet_path: Path) -> List[Dict[str, str]]:
    with open(sheet_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def build_deduped_question_rows(rows: List[Dict[str, str]], logger: Logger) -> List[Dict[str, str]]:
    """
    Deduplicate to one row per QuestionId, keeping only REQUIRED_SHEET_COLUMNS.
    Keeps the first occurrence of each QuestionId.
    """
    seen: Dict[str, Dict[str, str]] = {}
    # QuestionId-level IsSuccess gate:
    # - If ANY row for a QuestionId has IsSuccess == False -> overall False (skip processing later)
    # - Else if we see at least one True -> overall True
    # - Else keep empty / as-is
    is_success_gate: Dict[str, Optional[bool]] = {}

    for row in rows:
        qid = (row.get("QuestionId") or "").strip()
        if not qid:
            continue

        raw_is_success = (row.get("IsSuccess") or "").strip().lower()
        if raw_is_success == "false":
            is_success_gate[qid] = False
        elif raw_is_success == "true":
            # Only set True if not already locked to False
            if is_success_gate.get(qid) is None:
                is_success_gate[qid] = True

        if qid in seen:
            continue
        kept = {}
        for col in REQUIRED_SHEET_COLUMNS:
            kept[col] = (row.get(col) or "").strip()
        seen[qid] = kept

    # Apply the QuestionId-level IsSuccess gate to the deduped rows
    for qid, kept in seen.items():
        gate_val = is_success_gate.get(qid)
        if gate_val is True:
            kept["IsSuccess"] = "True"
        elif gate_val is False:
            kept["IsSuccess"] = "False"
        else:
            kept["IsSuccess"] = (kept.get("IsSuccess") or "").strip()

    deduped = list(seen.values())
    logger.info(f"Deduped questions_updated_sheet.csv to {len(deduped)} unique QuestionId rows")
    return deduped


def write_questions_sheet(sheet_path: Path, rows: List[Dict[str, str]]) -> None:
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    with open(sheet_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_SHEET_COLUMNS)
        writer.writeheader()
        for row in rows:
            out_row = {col: (row.get(col, "") or "") for col in OUTPUT_SHEET_COLUMNS}
            writer.writerow(out_row)


@dataclass
class QuestionResult:
    is_success: bool
    error_type: str = ""
    error_message: str = ""
    warning_message: str = ""


def stringify_messages(msgs: List[str]) -> str:
    msgs = [m.strip() for m in msgs if isinstance(m, str) and m.strip()]
    return " | ".join(msgs)


def clean_json_in_place(json_path: Path, cleaner_module, logger: Logger) -> None:
    """
    Run the HTML cleaner on a single JSON file and overwrite it.
    """
    data = load_json_file(json_path)
    language_code = data.get("language", "").strip().lower()
    cleaned = cleaner_module.clean_html_attributes(data, language_code)
    save_json_file(cleaned, json_path)
    logger.debug(f"Cleaned HTML attributes: {json_path}")


def process_question_json(
    question_id: str,
    json_path: Path,
    cleaner_module,
    logger: Logger,
) -> QuestionResult:
    filename = json_path.name

    if not json_path.exists():
        return QuestionResult(
            is_success=False,
            error_type="File",
            error_message=f"Target JSON not found: {json_path}",
        )

    # Step 1: HTML cleaning (must run before conversion)
    try:
        clean_json_in_place(json_path, cleaner_module, logger)
    except Exception as e:
        return QuestionResult(
            is_success=False,
            error_type="HTML Cleaning",
            error_message=f"Failed to clean HTML before conversion: {str(e)}",
        )

    # Reload after cleaning for conversion pipeline
    json_data = load_json_file(json_path)

    # Step 2: Pre-conversion validation (collect warnings even if valid)
    is_valid, errors, warnings = validate_pre_conversion(json_data, filename)
    warning_msg = stringify_messages(warnings)

    if not is_valid:
        return QuestionResult(
            is_success=False,
            error_type=ERROR_TYPES["PRE_VALIDATION"],
            error_message=stringify_messages(errors) or "Pre-validation failed",
            warning_message=warning_msg,
        )

    # Step 3: Convert
    try:
        converted_json = convert_question(json_data, filename)
    except (ValidationError, ConversionError) as e:
        return QuestionResult(
            is_success=False,
            error_type=ERROR_TYPES["CONVERSION"],
            error_message=str(e),
            warning_message=warning_msg,
        )
    except Exception as e:
        return QuestionResult(
            is_success=False,
            error_type=ERROR_TYPES["CONVERSION"],
            error_message=f"Unexpected conversion error: {str(e)}",
            warning_message=warning_msg,
        )

    # Step 4: Post-conversion validation
    is_valid_post, post_errors = validate_post_conversion(converted_json)
    if not is_valid_post:
        return QuestionResult(
            is_success=False,
            error_type=ERROR_TYPES["POST_VALIDATION"],
            error_message=stringify_messages(post_errors) or "Post-validation failed",
            warning_message=warning_msg,
        )

    # Step 5: Save converted JSON in-place (Step5_OUTPUT/.../Updated/<qid>.json)
    save_json_file(converted_json, json_path)
    return QuestionResult(is_success=True, warning_message=warning_msg)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step4_OUTPUT -> Step5_OUTPUT JSON cleaning + conversion workflow",
    )
    parser.add_argument(
        "--inputstep",
        "-i",
        type=str,
        default="Step4_OUTPUT",
        help="Input Step4_OUTPUT folder (default: Step4_OUTPUT)",
    )
    parser.add_argument(
        "--outputstep",
        "-o",
        type=str,
        default="Step5_OUTPUT",
        help="Output Step5_OUTPUT folder (default: Step5_OUTPUT)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    # Keep paths relative unless user passes absolute
    step4_dir = Path(args.inputstep)
    step5_dir = Path(args.outputstep)

    # Must empty Step5 before we create the Step5 log file (otherwise it gets deleted)
    empty_directory(step5_dir)

    date, stamp = _now_step_style_stamp()
    log_path = step5_dir / f"Step5_JsonCleaningAndConversion_{date}_{stamp}.log"
    logger = Logger(log_path=log_path, verbose=args.verbose)

    logger.info("=" * 80)
    logger.info("STEP5 JSON CLEANING + CONVERSION WORKFLOW")
    logger.info("=" * 80)
    logger.info(f"Step4_INPUT: {step4_dir}")
    logger.info(f"Step5_OUTPUT: {step5_dir}")
    logger.info(f"Log file: {log_path}")
    logger.info(f"Step5 folder emptied: {step5_dir}")

    # 1) Copy Step4 -> Step5 (excluding logs)
    copy_step4_to_step5(step4_dir, step5_dir, logger)

    # 2) Load and rewrite questions_updated_sheet.csv in Step5
    sheet_path = step5_dir / "questions_updated_sheet.csv"
    if not sheet_path.exists():
        logger.info(f"ERROR: questions_updated_sheet.csv not found in Step5: {sheet_path}")
        sys.exit(1)

    logger.info(f"Reading CSV: {sheet_path}")
    original_rows = read_questions_sheet(sheet_path)
    question_rows = build_deduped_question_rows(original_rows, logger)

    # Initialize output columns
    for row in question_rows:
        # Keep IsSuccess from Step4 sheet (it is the processing gate)
        row.setdefault("IsSuccess", "")
        row.setdefault("Error Message", "")
        row.setdefault("Error Type", "")
        row.setdefault("Warning Message", "")
        row.setdefault("tex_cleaning", "")

    # 3) Load HTML cleaning module (relative path)
    cleaner_path = Path("SIDE_TOOLS") / "jsons_htmltags_cleaning" / "clean_json_html.py"
    cleaner_module = load_cleaner_module(cleaner_path)
    logger.info(f"Loaded HTML cleaner from: {cleaner_path}")

    # 4) Process each question JSON in Step5 in-place
    total = len(question_rows)
    success = 0
    failed = 0
    skipped = 0

    logger.info(f"Processing {total} questions...")

    for idx, row in enumerate(question_rows, 1):
        qid = row.get("QuestionId", "").strip()
        if not qid:
            continue

        # Process only rows that were originally IsSuccess=True.
        # If IsSuccess is False, do NOT touch the JSON and do NOT change the row.
        if (row.get("IsSuccess") or "").strip().lower() != "true":
            skipped += 1
            logger.debug(f"SKIP [{qid}]: IsSuccess is not True in input sheet")
            continue

        updated_dir = step5_dir / qid / "Updated"
        json_path = updated_dir / f"{qid}.json"

        # Clean tex files before processing
        tex_cleaning_msg = clean_tex_files(qid, updated_dir, logger)
        row["tex_cleaning"] = tex_cleaning_msg
        if tex_cleaning_msg and "Error" not in tex_cleaning_msg and "No tex folder" not in tex_cleaning_msg:
            logger.debug(f"TEX CLEANING [{qid}]: {tex_cleaning_msg}")

        try:
            result = process_question_json(qid, json_path, cleaner_module, logger)
        except Exception as e:
            result = QuestionResult(
                is_success=False,
                error_type="Unexpected",
                error_message=str(e),
            )

        row["IsSuccess"] = "True" if result.is_success else "False"
        row["Error Message"] = result.error_message
        row["Error Type"] = result.error_type
        row["Warning Message"] = result.warning_message

        if result.is_success:
            success += 1
            if result.warning_message:
                logger.info(f"WARNING [{qid}]: {result.warning_message}")
            logger.debug(f"SUCCESS [{qid}]: {json_path}")
        else:
            failed += 1
            logger.info(
                f"FAILED  [{qid}]: {result.error_type} - {result.error_message}"
            )
            if result.warning_message:
                logger.info(f"  WARNINGS [{qid}]: {result.warning_message}")

        if idx % 100 == 0 or idx == total:
            logger.info(
                f"Progress: {idx}/{total} (success={success}, failed={failed}, skipped={skipped})"
            )

    # 5) Write updated CSV in Step5 (overwrite)
    logger.info(f"Writing updated CSV (one row per QuestionId): {sheet_path}")
    write_questions_sheet(sheet_path, question_rows)

    # 6) Summary
    logger.info("\n" + "=" * 80)
    logger.info("WORKFLOW SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total questions: {total}")
    logger.info(f"Success:         {success}")
    logger.info(f"Failed:          {failed}")
    logger.info(f"Skipped:         {skipped}")
    logger.info("=" * 80)

    if failed > 0:
        logger.info("Some questions failed. Check the CSV columns and the log for details.")
        sys.exit(1)
    else:
        logger.info("All questions processed successfully.")
        sys.exit(0)


if __name__ == "__main__":
    main()


