import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List

from SCRIPTS.config import (
    LANGUAGES, COUNTRIES, DEFAULT_SOURCE
)


class ValidationError(Exception):
    """Custom exception for validation errors"""
    def __init__(self, message: str, field: str = "", actual_value: Any = None, expected: str = ""):
        self.message = message
        self.field = field
        self.actual_value = actual_value
        self.expected = expected
        super().__init__(self.message)


class ConversionError(Exception):
    """Custom exception for conversion errors"""
    def __init__(self, message: str, part_type: str = ""):
        self.message = message
        self.part_type = part_type
        super().__init__(self.message)


def normalize_text(text: str) -> str:
    """Remove extra newlines and spaces from the text."""
    return re.sub(r'\s+', ' ', text).strip()


def format_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_empty_or_none(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    if isinstance(value, dict) and len(value) == 0:
        return True
    return False


def load_json_file(filepath: Path) -> Dict[str, Any]:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON format: {str(e)}", "file", filepath.name, "Valid JSON")
    except Exception as e:
        raise ValidationError(f"Failed to read file: {str(e)}", "file", filepath.name, "Readable file")


def save_json_file(data: Dict[str, Any], filepath: Path, pretty: bool = True) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        if pretty:
            json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            json.dump(data, f, ensure_ascii=False)


def extract_language_code(json_data: Dict[str, Any]) -> str:
    lang_code = json_data.get('language') or json_data.get('metadata', {}).get('language')
    if isinstance(lang_code, str) and not is_empty_or_none(lang_code):
        lang_code = lang_code.lower().strip()
        if lang_code in LANGUAGES:
            return lang_code
    
    raise ValidationError(
        "No valid language code found",
        "language",
        lang_code,
        f"One of: {', '.join(LANGUAGES.keys())}"
    )


def extract_country_code(json_data: Dict[str, Any]) -> str:
    # 1. Define candidates in standard priority order
    raw_candidates = [
        json_data.get('country'),
        json_data.get('metadata', {}).get('country')
    ]

    # 2. Collect ALL valid, normalized codes found in the input
    valid_found_codes = []
    for code in raw_candidates:
        if isinstance(code, str) and not is_empty_or_none(code):
            norm = code.lower().strip()
            if norm in COUNTRIES:
                valid_found_codes.append(norm)

    # 3. Apply the specific priority logic
    if valid_found_codes:
        # Rule 1: If 'eg' was found anywhere (top level or metadata), it wins.
        if "eg" in valid_found_codes:
            return "eg"
        
        # Rule 2: Otherwise, return the first one found (preserves Top Level priority)
        return valid_found_codes[0]

    # 4. Error Handling (No valid codes found)
    found_value = json_data.get('country') or json_data.get('metadata', {}).get('country')

    raise ValidationError(
        "Invalid country code",
        "country",
        found_value,
        f"One of: {', '.join(COUNTRIES.keys())}"
    )    


def extract_country_code_mandatory_return(json_data: Dict[str, Any]) -> str:
    # 1. Define candidates in standard priority order
    raw_candidates = [
        json_data.get('country'),
        json_data.get('metadata', {}).get('country')
    ]

    # 2. Collect ALL valid, normalized codes found in the input
    valid_found_codes = []
    for code in raw_candidates:
        if isinstance(code, str) and not is_empty_or_none(code):
            norm = code.lower().strip()
            if norm in COUNTRIES:
                valid_found_codes.append(norm)

    # 3. Apply the specific priority logic
    if valid_found_codes:
        # Rule 1: If 'eg' was found anywhere (top level or metadata), it wins.
        if "eg" in valid_found_codes:
            return "eg"
        
        # Rule 2: Otherwise, return the first one found (preserves Top Level priority)
        return valid_found_codes[0]

    # 4. Error Handling (No valid codes found)
    found_value = json_data.get('country') or json_data.get('metadata', {}).get('country')

    return found_value


def validate_id_consistency(json_data: Dict[str, Any], filename: str) -> str:
    mapped_id = str(json_data.get('metadata', {}).get('mapped_id', '')).strip()
    question_id = str(json_data.get('question_id', '')).strip()
    file_id = filename.replace('.json', '').strip()
    
    if is_empty_or_none(mapped_id):
        raise ValidationError(
            f"Missing metadata.mapped_id",
            "metadata.mapped_id",
            "missing",
            "Non-empty ID"
        )
    
    if not(mapped_id == question_id == file_id):
        raise ValidationError(
            f"ID mismatch: mapped_id={mapped_id}, question_id={question_id}, filename={file_id}",
            "metadata.mapped_id",
            f"mapped_id={mapped_id}, question_id={question_id}, file={file_id}",
            "Mapped ID, question ID, and filename must match"
        )
    
    return mapped_id


def extract_parent_id(json_data: Dict[str, Any]) -> Optional[str]:
    meta_id = str(json_data.get('metadata', {}).get('id', '')).strip()
    
    if is_empty_or_none(meta_id):
        meta_id = None

        raise ValidationError(
            f"Invalid parent_id",
            "parent_id",
            meta_id,
            "Valid parent ID"
        )

    return meta_id


def detect_question_types(json_data: Dict[str, Any]) -> List[str]:
    """
    Detect all part types in a question.
    Returns: List of part type strings
    """
    return [part.get('type', 'unknown') for part in json_data.get('parts', [])]


def get_source(json_data: Dict[str, Any]) -> str:
    return json_data.get('source', DEFAULT_SOURCE)


def extract_part_explanation(explanation: Any, part_index: int) -> Optional[str]:
    part_explanation = None
    if isinstance(explanation, str):
        part_explanation = f"<!--**Part {part_index} Explanation**-->{explanation}"
    # TODO: Implement the proper logic to extract the part explanation from the explanation string based on the part index and the explanation string structure so that we may use regex, str.split, beautifulsoup, or any other way that is appropriate for the task, or even an AI model response that splits the explanation string.
    return part_explanation