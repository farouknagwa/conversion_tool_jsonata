from typing import Dict, List, Any, Tuple
import re
from bs4 import BeautifulSoup

from SCRIPTS.config import (
    VALID_PART_TYPES, VALID_DIRECTIONS,
    VALID_CHOICE_TYPES, VALID_CONSTRAINT_TYPES,
    VALID_STRING_AI_TEMPLATE_IDS, GRID_SIZE_PATTERN
)
from SCRIPTS.utils import (
    validate_id_consistency, extract_language_code, extract_country_code, 
    extract_country_code_mandatory_return, is_empty_or_none
)

def validate_json_structure(json_data: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    Main validation function that validates the entire JSON structure.
    Matches the validateJsonStructure function from questionValidation.ts
    
    Args:
        json_data: The parsed JSON data
        
    Returns:
        Tuple of (errors, warnings) - errors cause validation failure, warnings don't
    """
    errors = []
    warnings = []
    
    # Validate top level structure
    if not json_data.get('parts', []) or not isinstance(json_data['parts'], list):
        errors.append("Missing or invalid 'parts' array")
        return errors, warnings  # Stop validation if parts array is missing
    
    if len(json_data.get('parts', [])) == 0:
        errors.append("'parts' array cannot be empty")
        return errors, warnings
    
    # Check metadata
    if not json_data.get('metadata', {}) or not isinstance(json_data['metadata'], dict):
        errors.append("Missing or invalid 'metadata' object")
    
    # Validate statement for multipart questions (WARNING only)
    if len(json_data.get('parts', [])) > 1 and not json_data.get('statement'):
        warnings.append("Multipart questions should have a 'statement' field")
    
    country_code = extract_country_code_mandatory_return(json_data)
    
    # Validate each part
    for i, part in enumerate(json_data.get('parts', [])):
        part_errors = _validate_part(part, i + 1, country_code)
        errors.extend(part_errors)
    
    # Validate root answer for explanation
    answer_errors, answer_warnings = _validate_root_answer_for_explanation(json_data)
    errors.extend(answer_errors)
    warnings.extend(answer_warnings)
    
    return errors, warnings


def _validate_part(part: Dict[str, Any], part_number: int, country_code: str) -> List[str]:
    """
    Validate a specific part of the question.
    Matches the validatePart function from questionValidation.ts
    
    Args:
        part: The part object to validate
        part_number: The number of the part (for error messages)
        
    Returns:
        List of error messages
    """
    errors = []
    
    # Check required fields for all parts
    required_fields = ["n", "type", "stem", "standalone"]
    for field in required_fields:
        if field not in part:
            errors.append(f"Part {part_number}: Missing required field '{field}'")
    
    # Check if part number matches index
    if part.get('n') != part_number:
        errors.append(
            f"Part {part_number}: Part number 'n' ({part.get('n')}) does not match its position"
        )
    
    # Validate type
    if part.get('type') not in VALID_PART_TYPES:
        errors.append(f"Part {part_number}: Invalid type '{part.get('type')}'")
        return errors  # Stop validation for this part if type is invalid
    
    # Validate stem
    if not part.get('stem') or not isinstance(part.get('stem'), str):
        errors.append(f"Part {part_number}: Invalid or missing 'stem' field")
        
    # Validate specific part types
    part_type = part.get('type')
    
    if part_type == "mcq":
        errors.extend(_validate_mcq(part, part_number, country_code))
    elif part_type == "mrq":
        errors.extend(_validate_mrq(part, part_number))
    elif part_type in ["frq", "frq_ai"]:
        errors.extend(_validate_frq_ai(part, part_number))
    elif part_type == "oq":
        errors.extend(_validate_oq(part, part_number))
    elif part_type == "gapText":
        errors.extend(_validate_gap_text(part, part_number))
    elif part_type == "string":
        errors.extend(_validate_string(part, part_number))
    elif part_type == "opinion":
        errors.extend(_validate_opinion(part, part_number))
    elif part_type == "matching":
        errors.extend(_validate_matching(part, part_number))
    elif part_type == "gmrq":
        errors.extend(_validate_gmrq(part, part_number))
    elif part_type == "counting":
        errors.extend(_validate_counting(part, part_number))
    elif part_type == "puzzle":
        errors.extend(_validate_puzzle(part, part_number))
    elif part_type == "input_box":
        errors.extend(_validate_input_box(part, part_number))
    
    return errors


def _validate_choice(choice: Dict[str, Any], choice_index: int, part_number: int, part_type: str) -> List[str]:
    """
    Validate common choice properties.
    Matches the validateChoice function from questionValidation.ts
    
    Args:
        choice: Choice object to validate
        choice_index: Index of the choice
        part_number: Part number for error messages
        part_type: Type of the part (mcq, mrq, oq, opinion, matching, counting, puzzle, input_box)
    Returns:
        List of error messages
    """
    errors = []
    
    # Check required fields
    required_fields = [
        "type", "html_content", "values", "unit", "index", "fixed_order"
    ]
    
    for field in required_fields:
        # Unit can be null, just needs to exist as a key
        if field not in choice:
            errors.append(
                f"Part {part_number} ({part_type}), Choice {choice_index + 1}: Missing required field '{field}'"
            )
    
    # Validate choice type
    if part_type in ["mcq", "mrq", "gmrq"] and choice.get('type') not in VALID_CHOICE_TYPES:
        errors.append(
            f"Part {part_number} ({part_type}), Choice {choice_index + 1}: Invalid choice type '{choice.get('type')}'"
        )
    
    # Validate html_content
    if not isinstance(choice.get('html_content'), str) or not choice.get('html_content', '').strip():
        errors.append(
            f"Part {part_number} ({part_type}), Choice {choice_index + 1}: Invalid or empty 'html_content'"
        )
    
    # Validate values
    if not isinstance(choice.get('values'), list):
        errors.append(
            f"Part {part_number} ({part_type}), Choice {choice_index + 1}: 'values' must be an array"
        )
    
    # Validate unit
    unit = choice.get('unit')
    if unit is not None and not isinstance(unit, str):
        errors.append(
            f"Part {part_number} ({part_type}), Choice {choice_index + 1}: 'unit' must be null or a string"
        )
    
    # Validate index
    index = choice.get('index')
    if not isinstance(index, int) or index < 0:
        errors.append(
            f"Part {part_number} ({part_type}), Choice {choice_index + 1}: 'index' must be a non-negative number"
        )
    
    # Validate fixed_order
    fixed_order = choice.get('fixed_order')
    if not isinstance(fixed_order, int) or fixed_order < 1:
        errors.append(
            f"Part {part_number} ({part_type}), Choice {choice_index + 1}: 'fixed_order' must be a positive number"
        )
    
    # Validate last_order
    if not is_empty_or_none(choice.get('last_order')):
        if not isinstance(choice.get('last_order'), bool):
            errors.append(
                f"Part {part_number} ({part_type}), Choice {choice_index + 1}: 'last_order' must be a boolean"
            )
    
    return errors


def _validate_mcq(part: Dict[str, Any], part_number: int, country_code: str) -> List[str]:
    """Validate MCQ (Multiple Choice Question) part"""
    errors = []
    
    # Validate choices array
    if not isinstance(part.get('choices'), list) or len(part.get('choices', [])) == 0:
        errors.append(f"Part {part_number} (mcq): 'choices' must be a non-empty array")
        return errors
    
    # Count keys
    key_choices = [c for c in part['choices'] if c.get('type') == 'key']
    if len(key_choices) != 1:
        errors.append(
            f"Part {part_number} (mcq): Must have exactly 1 key choice, found {len(key_choices)}"
        )

    # Count EG MCQ choices
    choices_count = len(part['choices'])
    if country_code == "eg" and choices_count > 4:
        errors.append(
            f"Part {part_number} (mcq): Must have at most 4 choices, found {choices_count} as country is Egypt"
        )
    
    # Validate each choice
    for i, choice in enumerate(part['choices']):
        errors.extend(_validate_choice(choice, i, part_number, 'mcq'))
    
    return errors


def _validate_mrq(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate MRQ (Multiple Response Question) part"""
    errors = []
    
    # Validate choices array
    if not isinstance(part.get('choices'), list) or len(part.get('choices', [])) == 0:
        errors.append(f"Part {part_number} (mrq): 'choices' must be a non-empty array")
        return errors
    
    # Must have at least 2 key choices
    key_choices = [c for c in part['choices'] if c.get('type') == 'key']
    if len(key_choices) < 2:
        errors.append(f"Part {part_number} (mrq): Must have at least 2 key choices, found {len(key_choices)}")
    
    # Validate each choice
    for i, choice in enumerate(part['choices']):
        errors.extend(_validate_choice(choice, i, part_number, 'mrq'))
    
    return errors


def _validate_frq_ai(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate FRQ AI part"""
    errors = []
    
    # Validate choices array
    if not isinstance(part.get('choices'), list):
        errors.append(
            f"Part {part_number} (frq_ai): 'choices' must be an empty array"
        )
    elif len(part.get('choices', [])) > 0:
        errors.append(
            f"Part {part_number} (frq_ai): 'choices' must be empty for frq_ai"
        )
    
    # Validate answer field
    if not part.get('answer') or not isinstance(part.get('answer'), str):
        errors.append(
            f"Part {part_number} (frq_ai): 'answer' field is required and must be a string"
        )
    
    # Validate ai object
    if not part.get('ai') or not isinstance(part.get('ai'), dict):
        errors.append(
            f"Part {part_number} (frq_ai): 'ai' field is required and must be an object"
        )
        return errors
    
    # Validate required AI fields
    if not part['ai'].get('ai_template_id'):
        errors.append(f"Part {part_number} (frq_ai): 'ai.ai_template_id' is required")

    ai_template_id = part['ai'].get('ai_template_id')

    # 1. Check if it exists (handles None, empty string, or 0)
    if is_empty_or_none(ai_template_id):
        errors.append(f"Part {part_number} (frq_ai): 'ai.ai_template_id' is required")
    # 2. Check if it is a valid 12-digit number (Safe for both int and str input)
    elif not (str(ai_template_id).isdigit() and len(str(ai_template_id)) == 12):
        errors.append(f"Part {part_number} (frq_ai): 'ai.ai_template_id' must be exactly 12 digits")

    # TODO: Validate ai.ai_template_id per subject and grade if required
    
    return errors


def _validate_oq(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate OQ (Ordering Question) part"""
    errors = []
    
    # Validate choices array
    if not isinstance(part.get('choices'), list) or len(part.get('choices', [])) == 0:
        errors.append(f"Part {part_number} (oq): 'choices' must be a non-empty array")
        return errors
    
    # All choices must be distractor type
    non_distractor = [c for c in part['choices'] if c.get('type') != 'distractor']
    if non_distractor:
        errors.append(
            f"Part {part_number} (oq): All choices must have type 'distractor'"
        )
    
    # Validate direction field
    if not part.get('direction') or part.get('direction') not in VALID_DIRECTIONS:
        errors.append(
            f"Part {part_number} (oq): 'direction' must be 'vertical' or 'horizontal'"
        )
    
    # Validate each choice
    for i, choice in enumerate(part['choices']):
        errors.extend(_validate_choice(choice, i, part_number, 'oq'))
    
    return errors


def _validate_gap_text(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate GapText (Fill-in-the-blank) part"""
    errors = []
    
    # Validate choices array
    if not isinstance(part.get('choices'), list):
        errors.append(f"Part {part_number} (gapText): 'choices' must be an empty array")
    elif len(part.get('choices', [])) > 0:
        errors.append(f"Part {part_number} (gapText): 'choices' must be empty for gapText")
    
    # Validate gap_text_keys
    if not isinstance(part.get('gap_text_keys'), list) or len(part.get('gap_text_keys', [])) == 0:
        errors.append(
            f"Part {part_number} (gapText): 'gap_text_keys' must be a non-empty array"
        )
        return errors
    
    # Validate gap_text_keys structure
    for i, key in enumerate(part['gap_text_keys']):
        if not key.get('value') or not isinstance(key.get('value'), str):
            errors.append(
                f"Part {part_number} (gapText): gap_text_key at index {i} must have a 'value' property"
            )
        
        if 'correct_order' in key:
            if not isinstance(key['correct_order'], int) or key['correct_order'] < 1:
                errors.append(
                    f"Part {part_number} (gapText): 'correct_order' at index {i} must be a positive number"
                )
    
    # Check if stem has gaps
    stem_gaps_count = part.get('stem', '').count('data-node-variation="gap"')
    
    if stem_gaps_count == 0:
        errors.append(
            f"Part {part_number} (gapText): stem must have at least one gap."
        )
    else:
        # Check if we have enough gap_text_keys
        gapped_text_keys_count = len(part['gap_text_keys'])
        if gapped_text_keys_count < stem_gaps_count:
            errors.append(
                f"Part {part_number} (gapText): 'gap_text_keys' found: {gapped_text_keys_count}, expected at least: {stem_gaps_count}"
            )
        
        # Check if we have enough correct_order keys
        correct_gapped_text_keys_count = len([k for k in part['gap_text_keys'] if 'correct_order' in k])
        if correct_gapped_text_keys_count != stem_gaps_count:
            errors.append(
                f"Part {part_number} (gapText): 'correct_order' found: {correct_gapped_text_keys_count}, expected: {stem_gaps_count}"
            )
    
    return errors


def _validate_string(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate String input part"""
    errors = []
    
    # Validate choices field
    if part.get('choices') is not None:
        errors.append(f"Part {part_number} (string): 'choices' must be null")
    
    # Validate answer field
    if not isinstance(part.get('answer'), list):
        errors.append(
            f"Part {part_number} (string): 'answer' must be an array of strings"
        )
    else:
        # Check each answer is a string
        for i, ans in enumerate(part['answer']):
            if not isinstance(ans, str):
                errors.append(
                    f"Part {part_number} (string): answer at index {i} must be a string"
                )
        
        # If string ai, check for valid string ai template id
        if part.get('ai', {}).get('ai_template_id'):
            ai_template_id = str(part['ai']['ai_template_id'])
            if ai_template_id not in VALID_STRING_AI_TEMPLATE_IDS:
                errors.append(
                    f"Part {part_number} (string): 'ai_template_id' is not a valid string ai template id."
                )
    
    return errors


def _validate_opinion(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate Opinion part"""
    errors = []
    
    # Validate choices array
    if not isinstance(part.get('choices'), list) or len(part.get('choices', [])) == 0:
        errors.append(
            f"Part {part_number} (opinion): 'choices' must be a non-empty array"
        )
        return errors
    
    # All choices must be distractor type
    non_distractor = [c for c in part['choices'] if c.get('type') != 'distractor']
    if non_distractor:
        errors.append(
            f"Part {part_number} (opinion): All choices must have type 'distractor'"
        )
    
    # Validate each choice
    for i, choice in enumerate(part['choices']):
        errors.extend(_validate_choice(choice, i, part_number, 'opinion'))
    
    return errors


def _validate_matching(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate Matching part"""
    errors = []
    
    # Validate choices array
    if not isinstance(part.get('choices'), list) or len(part.get('choices', [])) == 0:
        errors.append(
            f"Part {part_number} (matching): 'choices' must be a non-empty array"
        )
        return errors
    
    # Check for groups
    groups = set(c.get('group') for c in part['choices'] if c.get('group') is not None)
    if len(groups) != 2:
        errors.append(
            f"Part {part_number} (matching): Must have exactly 2 groups, found {len(groups)}"
        )
    
    # All choices must be distractor type
    non_distractor = [c for c in part['choices'] if c.get('type') != 'distractor']
    if non_distractor:
        errors.append(
            f"Part {part_number} (matching): All choices must have type 'distractor'"
        )
    
    # Validate each choice
    for i, choice in enumerate(part['choices']):
        errors.extend(_validate_choice(choice, i, part_number, 'matching'))
    
    return errors


def _validate_gmrq(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate Grouped Multiple Response Question (GMRQ) part"""
    errors = []
    
    # Validate choices array
    if not isinstance(part.get('choices'), list) or len(part.get('choices', [])) == 0:
        errors.append(
            f"Part {part_number} (gmrq): 'choices' must be a non-empty array"
        )
        return errors
    
    # Check for groups
    groups = set(c.get('group') for c in part['choices'] if c.get('group') is not None)
    if len(groups) != 2:
        errors.append(
            f"Part {part_number} (gmrq): Must have exactly 2 groups, found {len(groups)}"
        )
    
    # Check that each group has at least one key choice
    group1_choices = [c for c in part['choices'] if c.get('group') == 1]
    group2_choices = [c for c in part['choices'] if c.get('group') == 2]
    
    group1_keys = [c for c in group1_choices if c.get('type') == 'key']
    group2_keys = [c for c in group2_choices if c.get('type') == 'key']
    
    if len(group1_keys) != 1:
        errors.append(
            f"Part {part_number} (gmrq): Group 1 must have exactly 1 key choice, found {len(group1_keys)}"
        )
    
    if len(group2_keys) != 1:
        errors.append(
            f"Part {part_number} (gmrq): Group 2 must have exactly 1 key choice, found {len(group2_keys)}"
        )
    
    # Validate each choice has required fields (including is_correct)
    for i, choice in enumerate(part['choices']):
        # Validate group field
        if 'group' not in choice or choice.get('group') not in [1, 2]:
            errors.append(
                f"Part {part_number} (gmrq), Choice {i + 1}: 'group' must be 1 or 2"
            )
                
        # Validate common choice properties
        errors.extend(_validate_choice(choice, i, part_number, 'gmrq'))
    
    return errors


def _validate_counting(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate Counting part"""
    errors = []
    
    # Validate choices array
    if not isinstance(part.get('choices'), list):
        errors.append(
            f"Part {part_number} (counting): 'choices' must be an empty array"
        )
    elif len(part.get('choices', [])) > 0:
        errors.append(
            f"Part {part_number} (counting): 'choices' must be empty for counting"
        )
    
    # Validate answer field
    answer = part.get('answer')
    if not isinstance(answer, str) or not re.match(r'^\d+$', answer):
        errors.append(
            f"Part {part_number} (counting): 'answer' field must be a string representing a number"
        )
    
    # Validate grid_size field
    grid_size = part.get('grid_size')
    if not grid_size or not isinstance(grid_size, str) or not re.match(GRID_SIZE_PATTERN, grid_size):
        errors.append(
            f"Part {part_number} (counting): 'grid_size' must be a string in format 'rows×columns'"
        )
    
    return errors


def _validate_puzzle(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate Puzzle part"""
    errors = []
    
    # Validate choices array
    if not isinstance(part.get('choices'), list):
        errors.append(
            f"Part {part_number} (puzzle): 'choices' must be an empty array"
        )
    elif len(part.get('choices', [])) > 0:
        errors.append(
            f"Part {part_number} (puzzle): 'choices' must be empty for puzzle"
        )
    
    # Required puzzle fields
    required_fields = [
        "puzzleColumns", "puzzleImage", "puzzleImageHeight",
        "puzzleImageSplited", "puzzleImageWidth", "puzzleRows"
    ]
    
    for field in required_fields:
        if part.get(field) is None:
            errors.append(
                f"Part {part_number} (puzzle): Missing required field '{field}'"
            )
    
    # Validate puzzleColumns and puzzleRows
    if part.get('puzzleColumns') and not re.match(r'^\d+$', str(part['puzzleColumns'])):
        errors.append(
            f"Part {part_number} (puzzle): 'puzzleColumns' must be a string representing a number"
        )
    
    if part.get('puzzleRows') and not re.match(r'^\d+$', str(part['puzzleRows'])):
        errors.append(
            f"Part {part_number} (puzzle): 'puzzleRows' must be a string representing a number"
        )
    
    # Validate puzzleImage
    if part.get('puzzleImage') and not isinstance(part['puzzleImage'], str):
        errors.append(
            f"Part {part_number} (puzzle): 'puzzleImage' must be a string URL"
        )
    
    # Validate puzzleImageHeight and puzzleImageWidth
    if part.get('puzzleImageHeight') and not re.match(r'^\d+$', str(part['puzzleImageHeight'])):
        errors.append(
            f"Part {part_number} (puzzle): 'puzzleImageHeight' must be a string representing a number"
        )
    
    if part.get('puzzleImageWidth') and not re.match(r'^\d+$', str(part['puzzleImageWidth'])):
        errors.append(
            f"Part {part_number} (puzzle): 'puzzleImageWidth' must be a string representing a number"
        )
    
    # Validate puzzleImageSplited
    if not isinstance(part.get('puzzleImageSplited'), list) or len(part.get('puzzleImageSplited', [])) == 0:
        errors.append(
            f"Part {part_number} (puzzle): 'puzzleImageSplited' must be a non-empty array"
        )
    else:
        # Validate expected number of pieces
        rows = int(part['puzzleRows']) if part.get('puzzleRows') else 0
        cols = int(part['puzzleColumns']) if part.get('puzzleColumns') else 0
        expected_pieces = rows * cols if rows and cols else 0
        
        if expected_pieces > 0 and len(part['puzzleImageSplited']) != expected_pieces:
            errors.append(
                f"Part {part_number} (puzzle): Expected {expected_pieces} image pieces based on rows and columns, but found {len(part['puzzleImageSplited'])}"
            )
        
        # Validate each piece
        for i, piece in enumerate(part['puzzleImageSplited']):
            if not piece.get('index') or not isinstance(piece['index'], int):
                errors.append(
                    f"Part {part_number} (puzzle): Piece at index {i} is missing or has invalid 'index'"
                )
            
            if not piece.get('fixed_order') or not isinstance(piece['fixed_order'], int):
                errors.append(
                    f"Part {part_number} (puzzle): Piece at index {i} is missing or has invalid 'fixed_order'"
                )
            
            if not piece.get('correct_order') or not isinstance(piece['correct_order'], int):
                errors.append(
                    f"Part {part_number} (puzzle): Piece at index {i} is missing or has invalid 'correct_order'"
                )
            
            if not piece.get('src') or not isinstance(piece['src'], str):
                errors.append(
                    f"Part {part_number} (puzzle): Piece at index {i} is missing or has invalid 'src'"
                )
    
    return errors


def _validate_input_box(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate Input Box part"""
    errors = []
    
    # Validate choices array
    if not isinstance(part.get('choices'), list):
        errors.append(
            f"Part {part_number} (input_box): 'choices' must be an empty array"
        )
    elif len(part.get('choices', [])) > 0:
        errors.append(
            f"Part {part_number} (input_box): 'choices' must be empty for input_box"
        )
    
    # Validate answer field
    if not part.get('answer') or not isinstance(part.get('answer'), dict):
        errors.append(
            f"Part {part_number} (input_box): 'answer' field must be an object"
        )
        return errors
    
    # Validate answer.value
    if not part['answer'].get('value') or not isinstance(part['answer']['value'], str):
        errors.append(
            f"Part {part_number} (input_box): 'answer.value' must be a string"
        )
    
    # Validate constrains
    if not part['answer'].get('constrains') or not isinstance(part['answer']['constrains'], dict):
        errors.append(
            f"Part {part_number} (input_box): 'answer.constrains' must be an object"
        )
        return errors
    
    # Validate constrains.type
    if not part['answer']['constrains'].get('type') or part['answer']['constrains']['type'] not in VALID_CONSTRAINT_TYPES:
        errors.append(
            f"Part {part_number} (input_box): 'constrains.type' must be 'decimal' or 'integer'"
        )
    
    # Validate unit (optional)
    if 'unit' in part['answer'] and part['answer']['unit'] is not None and not isinstance(part['answer']['unit'], str):
        errors.append(
            f"Part {part_number} (input_box): 'answer.unit' must be a string or undefined"
        )
    
    return errors

def _validate_root_answer_for_explanation(json_data: Dict[str, Any]) -> List[str]:
    """Validate root answer for explanation"""
    errors = []
    warnings = []
    explanation = json_data.get('answer')
    number_of_parts = len(json_data.get('parts', []))
    
    if not is_empty_or_none(explanation) and isinstance(explanation, str):
        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(explanation, 'html.parser')
            if number_of_parts == 1: # For single part: must be only one <p> tag
                direct_children = [tag for tag in soup.children if tag.name is not None] # Get soup direct children             
                if len(direct_children) != 1:
                    warnings.append(
                        f"Root 'answer' field for single-part question must contain exactly one <p> tag, "
                        f"but found {len(direct_children)} top-level elements"
                    )
                elif direct_children[0].name != 'p':
                    warnings.append(
                        f"Root 'answer' field for single-part question must contain a <p> tag, "
                        f"but found <{direct_children[0].name}>"
                    )            
            elif number_of_parts > 1: # For multipart: must be one parent <div> with direct child <div>s equal to number_of_parts
                # Get all direct children of the soup
                direct_children = [tag for tag in soup.children if tag.name is not None] # Get soup direct children
                if len(direct_children) != 1:
                    errors.append(
                        f"Root 'answer' field for multipart question must contain exactly one parent <div>, "
                        f"but found {len(direct_children)} top-level elements"
                    )
                elif direct_children[0].name != 'div':
                    errors.append(
                        f"Root 'answer' field for multipart question must contain a parent <div>, "
                        f"but found <{direct_children[0].name}>"
                    )
                else: # Check the direct children of the parent div
                    parent_div = direct_children[0]
                    child_divs = [tag for tag in parent_div.children if tag.name == 'div']                    
                    if len(child_divs) != number_of_parts:
                        errors.append(
                            f"Root 'answer' field for multipart question must have {number_of_parts} "
                            f"direct child <div>s (one per part), but found {len(child_divs)}"
                        )        
        except Exception as e:
            errors.append(f"Error parsing root 'answer' field as HTML: {str(e)}")
    
    return errors, warnings


def validate_pre_conversion(json_data: Dict[str, Any], filename: str) -> Tuple[bool, List[str], List[str]]:
    """
    Main entry point for pre-conversion validation.
    Returns: Tuple of (is_valid, list_of_errors, list_of_warnings)
    """
    errors, warnings = validate_json_structure(json_data)
    
    try:
        # Validate ID consistency
        try:
            validate_id_consistency(json_data, filename)
        except Exception as e:
            errors.append(str(e))
        
        # Validate language code
        try:
            extract_language_code(json_data)
        except Exception as e:
            errors.append(str(e))
        
        # Validate country code
        try:
            extract_country_code(json_data)
        except Exception as e:
            errors.append(str(e))
    
    except ImportError:
        pass  # Tolerate import errors during testing
    
    return (len(errors) == 0, errors, warnings)

