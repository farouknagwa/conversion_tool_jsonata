from typing import Dict, List, Any, Tuple

from SCRIPTS.config import LANGUAGES, COUNTRIES


def _validate_root_fields(data: Dict[str, Any]) -> List[str]:
    """Validate root level fields of converted JSON"""
    errors = []
    
    # Required fields
    required_fields = [
        'question_id', 'language_code', 'language',
        'country_code', 'country', 'subject', 'grade',
        'number_of_parts', 'section_id', 'source', 'content'
    ]
    
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required root field: '{field}'")
    
    # Validate question_id is string
    if 'question_id' in data and not isinstance(data['question_id'], str):
        errors.append("'question_id' must be a string")
    
    # Validate parent_id (can be None or string)
    if 'parent_id' in data and data['parent_id'] is not None:
        if not isinstance(data['parent_id'], str):
            errors.append("'parent_id' must be null or a string")
    
    # Validate language_code
    if 'language_code' in data and data['language_code'] not in LANGUAGES:
        errors.append(f"Invalid language_code: '{data['language_code']}'")
    
    # Validate language matches language_code
    if 'language_code' in data and 'language' in data:
        expected_language = LANGUAGES.get(data['language_code'])
        if data['language'] != expected_language:
            errors.append(f"Language mismatch: got '{data['language']}', expected '{expected_language}'")
    
    # Validate country_code
    if 'country_code' in data and data['country_code'] is not None:
        if data['country_code'] not in COUNTRIES:
            errors.append(f"Invalid country_code: '{data['country_code']}'")
    
    # Validate country matches country_code
    if 'country_code' in data and 'country' in data:
        if data['country_code'] is not None:
            expected_country = COUNTRIES.get(data['country_code'])
            if data['country'] != expected_country:
                errors.append(f"Country mismatch: got '{data['country']}', expected '{expected_country}'")
    
    # Validate number_of_parts
    if 'number_of_parts' in data:
        if not isinstance(data['number_of_parts'], int) or data['number_of_parts'] < 1:
            errors.append("'number_of_parts' must be a positive integer")
    
    # Validate grade is string
    if 'grade' in data and not isinstance(data['grade'], str):
        errors.append("'grade' must be a string")
    
    # Validate section_id is string
    if 'section_id' in data and not isinstance(data['section_id'], str):
        errors.append("'section_id' must be a string")
    
    # Validate source is string
    if 'source' in data and not isinstance(data['source'], str):
        errors.append("'source' must be a string")
    
    return errors


def _validate_content(content: Dict[str, Any], number_of_parts: int) -> List[str]:
    """Validate content object"""
    errors = []
    
    # Validate parts array
    if 'parts' not in content:
        errors.append("Content missing 'parts' array")
        return errors
    
    if not isinstance(content['parts'], list):
        errors.append("'parts' must be an array")
        return errors
    
    if len(content['parts']) == 0:
        errors.append("'parts' array cannot be empty")
        return errors
    
    # Validate statement logic
    if number_of_parts > 1:
        if 'statement' not in content:
            errors.append("Multi-part questions must have 'statement' in content")
    else:
        if 'statement' in content:
            errors.append("Single-part questions should not have 'statement' in content")
    
    # Validate number of parts matches
    if len(content['parts']) != number_of_parts:
        errors.append(f"Parts count mismatch: content has {len(content['parts'])} parts but number_of_parts is {number_of_parts}")
    
    # Validate each part
    for i, part in enumerate(content['parts'], 1):
        errors.extend(_validate_part(part, i, number_of_parts))
    
    return errors


def _validate_part(part: Dict[str, Any], part_number: int, total_parts: int) -> List[str]:
    """Validate a converted part"""
    errors = []
    
    # Required fields for all parts
    required_fields = ['n', 'type', 'stem']
    for field in required_fields:
        if field not in part:
            errors.append(f"Part {part_number}: Missing required field '{field}'")
    
    # Validate n matches position
    if 'n' in part and part['n'] != part_number:
        errors.append(f"Part {part_number}: Part number 'n' ({part['n']}) does not match position")
    
    # Validate stem is string
    if 'stem' in part and not isinstance(part['stem'], str):
        errors.append(f"Part {part_number}: 'stem' must be a string")
    
    # Validate type-specific fields
    part_type = part.get('type')
    
    if part_type == 'counting':
        errors.extend(_validate_counting_part(part, part_number))
    elif part_type == 'frq':
        errors.extend(_validate_frq_part(part, part_number))
    elif part_type == 'gap':
        errors.extend(_validate_gap_part(part, part_number))
    elif part_type == 'input':
        errors.extend(_validate_input_part(part, part_number))
    elif part_type == 'matching':
        errors.extend(_validate_matching_part(part, part_number))
    elif part_type == 'mcq':
        errors.extend(_validate_mcq_part(part, part_number))
    elif part_type == 'mrq':
        errors.extend(_validate_mrq_part(part, part_number))
    elif part_type == 'opinion':
        errors.extend(_validate_opinion_part(part, part_number))
    elif part_type == 'ordering':
        errors.extend(_validate_ordering_part(part, part_number))
    elif part_type == 'puzzle':
        errors.extend(_validate_puzzle_part(part, part_number))
    elif part_type == 'string':
        errors.extend(_validate_string_part(part, part_number))
    
    return errors


def _validate_counting_part(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate counting type part"""
    errors = []
    
    if 'grid' not in part:
        errors.append(f"Part {part_number} (counting): Missing 'grid' object")
    elif isinstance(part['grid'], dict):
        if 'rows' not in part['grid'] or 'columns' not in part['grid']:
            errors.append(f"Part {part_number} (counting): 'grid' must have 'rows' and 'columns'")
        if not isinstance(part['grid'].get('rows'), int):
            errors.append(f"Part {part_number} (counting): 'grid.rows' must be an integer")
        if not isinstance(part['grid'].get('columns'), int):
            errors.append(f"Part {part_number} (counting): 'grid.columns' must be an integer")
    
    if 'correct_answer' not in part:
        errors.append(f"Part {part_number} (counting): Missing 'correct_answer'")
    elif not isinstance(part['correct_answer'], int):
        errors.append(f"Part {part_number} (counting): 'correct_answer' must be an integer")
    
    return errors


def _validate_frq_part(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate frq type part"""
    errors = []
    
    if 'acceptable_answers' not in part:
        errors.append(f"Part {part_number} (frq): Missing 'acceptable_answers'")
    elif not isinstance(part['acceptable_answers'], list):
        errors.append(f"Part {part_number} (frq): 'acceptable_answers' must be an array")

    # Validate ai_template_id
    if 'ai_template_id' not in part:
        errors.append(f"Part {part_number} (frq): 'ai_template_id' is required")
    else:
        t_id = part['ai_template_id']
        # 1. Check if it is a string
        if not isinstance(t_id, str):
            errors.append(f"Part {part_number} (frq): 'ai_template_id' must be a string")
        # 2. Check if it is exactly 12 digits
        elif not (t_id.isdigit() and len(t_id) == 12):
            errors.append(f"Part {part_number} (frq): 'ai_template_id' must be exactly 12 digits")

    return errors


def _validate_gap_part(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate gap type part"""
    errors = []
    
    if 'gap_keys' not in part:
        errors.append(f"Part {part_number} (gap): Missing 'gap_keys'")
    elif not isinstance(part['gap_keys'], list):
        errors.append(f"Part {part_number} (gap): 'gap_keys' must be an array")
    else:
        for i, key in enumerate(part['gap_keys']):
            if 'value' not in key:
                errors.append(f"Part {part_number} (gap): gap_key {i} missing 'value'")
            if 'display_order' not in key:
                errors.append(f"Part {part_number} (gap): gap_key {i} missing 'display_order'")
    
    if 'correct_answer' not in part:
        errors.append(f"Part {part_number} (gap): Missing 'correct_answer'")
    elif not isinstance(part['correct_answer'], str):
        errors.append(f"Part {part_number} (gap): 'correct_answer' must be a string")
    
    return errors


def _validate_input_part(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate input type part"""
    errors = []
    
    if 'correct_answer' not in part:
        errors.append(f"Part {part_number} (input): Missing 'correct_answer'")
    elif isinstance(part['correct_answer'], dict):
        if 'value' not in part['correct_answer']:
            errors.append(f"Part {part_number} (input): 'correct_answer.value' is required")
        if 'constraints' not in part['correct_answer']:
            errors.append(f"Part {part_number} (input): 'correct_answer.constraints' is required")
        elif isinstance(part['correct_answer']['constraints'], dict):
            if 'type' not in part['correct_answer']['constraints']:
                errors.append(f"Part {part_number} (input): 'constraints.type' is required")
    
    return errors


def _validate_matching_part(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate matching type part"""
    errors = []
    
    if 'items' not in part:
        errors.append(f"Part {part_number} (matching): Missing 'items'")
    elif isinstance(part['items'], dict):
        if 'A' not in part['items']:
            errors.append(f"Part {part_number} (matching): 'items.A' is required")
        if 'B' not in part['items']:
            errors.append(f"Part {part_number} (matching): 'items.B' is required")
        if 'correct_answer' not in part['items']:
            errors.append(f"Part {part_number} (matching): 'items.correct_answer' is required")
    
    return errors


def _validate_mcq_part(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate mcq type part"""
    errors = []
    
    if 'choices' not in part:
        errors.append(f"Part {part_number} (mcq): Missing 'choices'")
    elif not isinstance(part['choices'], list):
        errors.append(f"Part {part_number} (mcq): 'choices' must be an array")
    else:
        for i, choice in enumerate(part['choices']):
            if 'label' not in choice:
                errors.append(f"Part {part_number} (mcq): choice {i} missing 'label'")
            if 'value' not in choice:
                errors.append(f"Part {part_number} (mcq): choice {i} missing 'value'")
            if 'is_correct' not in choice:
                errors.append(f"Part {part_number} (mcq): choice {i} missing 'is_correct'")
    
    if 'correct_answer' not in part:
        errors.append(f"Part {part_number} (mcq): Missing 'correct_answer'")
    elif isinstance(part['correct_answer'], dict):
        if 'label' not in part['correct_answer'] or 'value' not in part['correct_answer']:
            errors.append(f"Part {part_number} (mcq): 'correct_answer' must have 'label' and 'value'")
    
    return errors


def _validate_mrq_part(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate mrq type part"""
    errors = []
    
    if 'choices' not in part:
        errors.append(f"Part {part_number} (mrq): Missing 'choices'")
    elif not isinstance(part['choices'], list):
        errors.append(f"Part {part_number} (mrq): 'choices' must be an array")
    
    if 'correct_answer' not in part:
        errors.append(f"Part {part_number} (mrq): Missing 'correct_answer'")
    elif not isinstance(part['correct_answer'], list):
        errors.append(f"Part {part_number} (mrq): 'correct_answer' must be an array")
    
    return errors


def _validate_opinion_part(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate opinion type part"""
    errors = []
    
    if 'choices' not in part:
        errors.append(f"Part {part_number} (opinion): Missing 'choices'")
    elif not isinstance(part['choices'], list):
        errors.append(f"Part {part_number} (opinion): 'choices' must be an array")
    
    # Opinion should NOT have correct_answer
    if 'correct_answer' in part:
        errors.append(f"Part {part_number} (opinion): Should not have 'correct_answer'")
    
    return errors


def _validate_ordering_part(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate ordering type part"""
    errors = []
    
    if 'direction' not in part:
        errors.append(f"Part {part_number} (ordering): Missing 'direction'")
    elif part['direction'] not in ['vertical', 'horizontal']:
        errors.append(f"Part {part_number} (ordering): 'direction' must be 'vertical' or 'horizontal'")
    
    if 'items' not in part:
        errors.append(f"Part {part_number} (ordering): Missing 'items'")
    elif not isinstance(part['items'], list):
        errors.append(f"Part {part_number} (ordering): 'items' must be an array")
    
    if 'correct_answer' not in part:
        errors.append(f"Part {part_number} (ordering): Missing 'correct_answer'")
    elif not isinstance(part['correct_answer'], list):
        errors.append(f"Part {part_number} (ordering): 'correct_answer' must be an array")
    
    return errors


def _validate_puzzle_part(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate puzzle type part"""
    errors = []
    
    if 'rows' not in part:
        errors.append(f"Part {part_number} (puzzle): Missing 'rows'")
    if 'columns' not in part:
        errors.append(f"Part {part_number} (puzzle): Missing 'columns'")
    
    if 'pieces' not in part:
        errors.append(f"Part {part_number} (puzzle): Missing 'pieces'")
    elif not isinstance(part['pieces'], list):
        errors.append(f"Part {part_number} (puzzle): 'pieces' must be an array")
    
    return errors


def _validate_string_part(part: Dict[str, Any], part_number: int) -> List[str]:
    """Validate string type part"""
    errors = []
    
    if 'ai_template_id' not in part:
        errors.append(f"Part {part_number} (string): Missing 'ai_template_id'")
    elif not isinstance(part['ai_template_id'], str):
        errors.append(f"Part {part_number} (string): 'ai_template_id' must be a string")
    
    if 'acceptable_answers' not in part:
        errors.append(f"Part {part_number} (string): Missing 'acceptable_answers'")
    elif not isinstance(part['acceptable_answers'], list):
        errors.append(f"Part {part_number} (string): 'acceptable_answers' must be an array")
    
    return errors


def validate_post_conversion(converted_json: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Main entry point for post-conversion validation.
    Validates that the converted JSON has correct structure and all required fields.
    Returns: Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Validate root level fields
    errors.extend(_validate_root_fields(converted_json))
    
    # Validate content structure
    if 'content' in converted_json:
        errors.extend(_validate_content(converted_json['content'], converted_json.get('number_of_parts', 0)))
    else:
        errors.append("Missing 'content' object")
    
    return (len(errors) == 0, errors)