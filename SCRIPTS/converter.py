from typing import Dict, List, Any
from pathlib import Path
import jsonata

from SCRIPTS.utils import (
    ValidationError, ConversionError,
    validate_id_consistency, extract_parent_id,
    extract_language_code, extract_country_code,
    get_source, is_empty_or_none, extract_part_explanation
)
from SCRIPTS.config import (
    LANGUAGES, COUNTRIES
)


def extract_common_metadata(json_data: Dict[str, Any], filename: str) -> Dict[str, Any]:
    question_id = validate_id_consistency(json_data, filename)
    parent_id = extract_parent_id(json_data)
    language_code = extract_language_code(json_data)
    language = LANGUAGES.get(language_code)
    country_code = extract_country_code(json_data)
    country = COUNTRIES.get(country_code)
    subject = json_data.get('subject')
    if is_empty_or_none(subject):
        raise ValidationError("Missing required field 'subject'", "subject", subject, "Non-empty string")
    subject_id = json_data.get('subject_id')
    if is_empty_or_none(subject_id):
        raise ValidationError("Missing required field 'subject_id'", "subject_id", subject_id, "Non-empty string")        
    grade = str(json_data.get('grade', ''))
    if is_empty_or_none(grade):
        raise ValidationError("Missing required field 'grade'", "grade", grade, "Non-empty string")        
    grade_id = str(json_data.get('grade_id', ''))
    if is_empty_or_none(grade_id):
        raise ValidationError("Missing required field 'grade_id'", "grade_id", grade_id, "Non-empty string")        
    section_id = str(json_data.get('section_id', ''))
    if is_empty_or_none(section_id):
        raise ValidationError("Missing required field 'section_id'", "section_id", section_id, "Non-empty string")    
    source = get_source(json_data)    
    number_of_parts = len(json_data.get('parts', []))
    
    return {
        "question_id": question_id,
        "parent_id": parent_id,
        "language_code": language_code,
        "language": language,
        "country_code": country_code,
        "country": country,
        "subject": subject,
        "subject_id": subject_id,
        "grade": grade,
        "grade_id": grade_id,
        "number_of_parts": number_of_parts,
        "section_id": section_id,
        "source": source
    }


def convert_part(part: Dict[str, Any], part_index: int, language_code: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a single part based on its type.
    Returns: Converted part in new structure        
    Raises: ConversionError: If conversion fails
    """
    part_type = part.get('type')

    explanation = json_data.get('answer')
    number_of_parts = len(json_data.get('parts', []))
    explanation = extract_part_explanation(explanation, number_of_parts, part_index)
    
    # All types now use JSONata conversion (return complete structure)
    jsonata_map = {
        'matching': 'matching',
        'mcq': 'mcq',
        'mrq': 'mrq',
        'opinion': 'opinion',
        'counting': 'counting',
        'oq': 'ordering',
        'string': 'string',
        'frq': 'frq',
        'frq_ai': 'frq',
        'gapText': 'gap',
        'input_box': 'input',
        'puzzle': 'puzzle',
        'gmrq': 'gmrq'
    }
    
    if part_type not in jsonata_map:
        raise ConversionError(f"Unknown part type: {part_type}", part_type)
    
    jsonata_file = jsonata_map[part_type]
    
    try:
        rule_path = Path(__file__).parent.parent / 'JSONATA_RULES' / f'{jsonata_file}.jsonata'
        with open(rule_path, 'r', encoding='utf-8') as f:
            jsonata_expression = f.read()
        
        # Execute JSONata transformation
        expr = jsonata.Jsonata(jsonata_expression)
        result = expr.evaluate({
            "part": part,
            "languageCode": language_code,
            "explanation": explanation
        })
        
        return result
    
    except Exception as e:
        raise ConversionError(f"JSONata conversion failed for {part_type} part: {str(e)}", part_type)


def build_final_json(metadata: Dict[str, Any], converted_parts: List[Dict[str, Any]], original_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the final converted JSON structure.    
    Args:
        metadata: Common metadata dictionary
        converted_parts: List of converted part objects
        original_json: Original JSON for extracting statement     
    Returns:
        Complete converted JSON structure
    """
    # Build content object
    content = dict() 
       
    # Add statement if multi-part
    if metadata['number_of_parts'] > 1:
        content['statement'] = original_json.get('statement', '')

    content["parts"] = converted_parts

    # Build final structure
    result = {
        "question_id": metadata['question_id'],
        "parent_id": metadata['parent_id'],
        "language_code": metadata['language_code'],
        "language": metadata['language'],
        "country_code": metadata['country_code'],
        "country": metadata['country'],
        "subject": metadata['subject'],
        "subject_id": metadata['subject_id'],
        "grade": metadata['grade'],
        "grade_id": metadata['grade_id'],
        "number_of_parts": metadata['number_of_parts'],
        "section_id": metadata['section_id'],
        "source": metadata['source'],
        "content": content
    }
    
    return result


def convert_question(json_data: Dict[str, Any], filename: str) -> Dict[str, Any]:
    """
    Main conversion function. Converts entire question from old to new structure.    
    Returns: Converted JSON in new structure        
    Raises: ValidationError: If data extraction fails, ConversionError: If conversion fails
    """
    # Extract common metadata
    metadata = extract_common_metadata(json_data, filename)
    
    # Convert each part
    converted_parts = []
    for i, part in enumerate(json_data.get('parts', []), 1):
        converted_part = convert_part(part, i, metadata['language_code'], json_data)
        converted_parts.append(converted_part)
    
    # Build final JSON
    final_json = build_final_json(metadata, converted_parts, json_data)
    
    return final_json