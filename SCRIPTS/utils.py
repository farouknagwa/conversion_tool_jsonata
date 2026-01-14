import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List
from bs4 import BeautifulSoup

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
    raw_candidate = json_data.get('country')

    if isinstance(raw_candidate, str) and not is_empty_or_none(raw_candidate):
        norm = raw_candidate.lower().strip()
        if norm in COUNTRIES:
            return norm

    raise ValidationError(
        "Invalid country code",
        "country",
        raw_candidate,
        f"One of: {', '.join(COUNTRIES.keys())}"
    )    


def extract_country_code_mandatory_return(json_data: Dict[str, Any]) -> str:
    raw_candidate = json_data.get('country')

    if isinstance(raw_candidate, str) and not is_empty_or_none(raw_candidate):
        norm = raw_candidate.lower().strip()
        if norm in COUNTRIES:
            return norm

    return raw_candidate


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


def extract_part_explanation(explanation: Any, number_of_parts: int, part_index: int) -> Optional[str]:
    """
    Extract the explanation for a specific part from the root answer field.
    
    For single-part questions: returns the entire explanation
    For multipart questions: extracts the corresponding child <div> based on part_index
    
    Args:
        explanation: The root answer/explanation field (HTML string)
        number_of_parts: Total number of parts in the question
        part_index: The part number (1-based index)
        
    Returns:
        The explanation for the specified part, or None if not available
    """
    part_explanation = None

    if not is_empty_or_none(explanation):
        explanation = normalize_text(explanation)

        if isinstance(explanation, str):
            if number_of_parts == 1:
                # For single-part questions, return the entire explanation
                part_explanation = explanation
            else:
                # For multipart questions, extract the specific child div
                try:
                    soup = BeautifulSoup(explanation, 'html.parser')
                    # Get all direct children of the soup
                    direct_children = [tag for tag in soup.children if tag.name is not None]
                    
                    if len(direct_children) == 1 and direct_children[0].name == 'div':
                        # This is the parent div
                        parent_div = direct_children[0]
                        # Get all direct child divs
                        child_divs = [tag for tag in parent_div.children if tag.name == 'div']
                        if len(child_divs) != number_of_parts:
                            return None
                        
                        # part_index is 1-based, so we need to subtract 1 for 0-based array indexing
                        if 0 < part_index <= len(child_divs):
                            # Get the specific child div and convert back to HTML string
                            target_div = child_divs[part_index - 1]
                            part_explanation = str(target_div)
                except Exception:
                    # If parsing fails, return None
                    part_explanation = None
                    
    return part_explanation


def remove_one_distractor(part: Dict[str, Any], threshold: int) -> bool:
    """
    Remove one distractor from MCQ/MRQ part if choices count >= threshold.
    
    Uses the same logic as Extra_Choices_Removal_and_Renumber.py:
    - Prefers removing distractors with last_order=False
    - Falls back to distractors with last_order=True if no others available
    
    Args:
        part: The part dictionary to modify
        threshold: Minimum number of choices to trigger removal (e.g., 5 means remove if >= 5)
    
    Returns:
        True if a distractor was removed, False otherwise
    """
    part_type = part.get('type', '')
    choices = part.get('choices', [])
    choices_len_before = len(choices) if isinstance(choices, list) else 0

    if part_type not in ['mcq', 'mrq'] or choices_len_before < threshold:
        return False

    distractors_not_last_idx = []
    distractors_last_idx = []

    for idx, ch in enumerate(choices):
        if not isinstance(ch, dict):
            return False
        if ch.get('type', '') == 'distractor':
            if ch.get('last_order', False):
                distractors_last_idx.append(idx)
            else:
                distractors_not_last_idx.append(idx)

    removed_idx = None
    if distractors_not_last_idx:
        removed_idx = distractors_not_last_idx[-1]
    elif distractors_last_idx:
        removed_idx = distractors_last_idx[-1]
    else:
        return False

    choices.pop(removed_idx)
    return True


def robust_renumber(part: Dict[str, Any]) -> None:
    """
    Renumber index and fixed_order fields of choices to ensure sequential numbering.
    
    - Renumbers index to be 0-based sequential: [0, 1, 2, ...]
    - Renumbers fixed_order to be 1-based sequential: [1, 2, 3, ...]
    
    Args:
        part: The part dictionary to modify (must have 'choices' list)
    """
    choices = part.get('choices', [])
    
    if not isinstance(choices, list) or not choices:
        return
    
    # Collect existing index and fixed_order values
    part_choice_indexes = []
    part_choice_fixed_orders = []
    
    for part_choice in choices:
        part_choice_index = part_choice.get('index', '')
        part_choice_fixed_order = part_choice.get('fixed_order', '')
        
        if not isinstance(part_choice_index, int) or not isinstance(part_choice_fixed_order, int):
            return  # Skip renumbering if invalid data types
        else:
            part_choice_indexes.append(part_choice_index)
            part_choice_fixed_orders.append(part_choice_fixed_order)
    
    # Check and renumber index if needed (0-based: 0, 1, 2, ...)
    if part_choice_indexes and part_choice_fixed_orders:
        if sorted(part_choice_indexes) != list(range(len(part_choice_indexes))):
            new_index_mapping = {old: new for new, old in enumerate(sorted(part_choice_indexes))}
            for part_choice in choices:
                part_choice['index'] = new_index_mapping[part_choice['index']]
        
        # Check and renumber fixed_order if needed
        # Check if sorted fixed_orders are NOT 0-based sequential, then renumber to 1-based sequential
        if sorted(part_choice_fixed_orders) != list(range(len(part_choice_fixed_orders))):
            new_fixed_order_mapping = {old: new for new, old in enumerate(sorted(part_choice_fixed_orders), 1)}
            for part_choice in choices:
                part_choice['fixed_order'] = new_fixed_order_mapping[part_choice['fixed_order']]