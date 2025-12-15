import json
import pandas as pd
from pathlib import Path
from typing import Dict, Any

class ValidationError(Exception):
    def __init__(self, message, field_type, field_name, expected_type):
        super().__init__(message)
        self.field_type = field_type
        self.field_name = field_name
        self.expected_type = expected_type

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

import shutil

def main():
    base_path = Path(__file__).parent
    inputs_dir = base_path / 'inputs'
    outputs_dir = base_path / 'outputs'
    csv_path = base_path / 'question_report_combined.csv'

    if not inputs_dir.exists():
        print(f"Inputs directory not found: {inputs_dir}")
        return

    if not csv_path.exists():
        print(f"CSV file not found: {csv_path}")
        return

    # Clear and recreate outputs directory
    if outputs_dir.exists():
        shutil.rmtree(outputs_dir)
    outputs_dir.mkdir()

    # Define and create expected subdirectories
    subdirs = [
        'counting', 'frq_ai', 'gapText', 'input_box', 
        'matching', 'mcq', 'mrq', 'multipart', 
        'opinion', 'oq', 'puzzle', 'string'
    ]
    
    for subdir in subdirs:
        (outputs_dir / subdir).mkdir(exist_ok=True)

    # Load CSV with all columns as strings (dtype=str)
    try:
        df = pd.read_csv(csv_path, dtype=str, encoding='utf-8')
    except Exception as e:
        print(f"Failed to load CSV: {e}")
        return

    files = list(inputs_dir.glob('*.json'))
    print(f"Found {len(files)} JSON files in inputs.")

    for filepath in files:
        try:
            json_data = load_json_file(filepath)
            
            # Determine destination folder
            parts = json_data.get('parts', [])
            if len(parts) > 1:
                category = 'multipart'
            elif len(parts) == 1:
                # Use the type of the single part
                category = parts[0].get('type', 'unknown')
            else:
                category = 'unknown'

            # Ensure category folder exists if it's new
            target_dir = outputs_dir / category
            if not target_dir.exists():
                print(f"Creating new category folder: {category}")
                target_dir.mkdir(exist_ok=True)

            # Extract mapped_id
            metadata = json_data.get('metadata', {})
            mapped_id = metadata.get('mapped_id')

            if mapped_id is None:
                print(f"Skipping metadata update for {filepath.name}: 'mapped_id' missing in metadata")
                save_json_file(json_data, target_dir / filepath.name)
                continue

            # mapped_id logic
            # Ensure mapped_id is string for comparison with DF which is loaded as str
            mapped_id_str = str(mapped_id)
            
            # Find rows
            # df['base_question_id'] matching mapped_id
            matches = df[df['base_question_id'] == mapped_id_str]

            if matches.empty:
                print(f"Warning: No match found for mapped_id {mapped_id_str} in CSV ({filepath.name})")
                save_json_file(json_data, target_dir / filepath.name)
                continue
            
            # Take the first match
            row = matches.iloc[0]

            # Prepare new data
            # "answer": null,
            # "section_id": <from the df>,
            # "language": <from the df>,
            # "subject_id": "123456789012",
            # "subject": <from the df>,
            # "grade_id": "123456789012",
            # "grade": <from the df>,
            # "country": <from the df>,
            # "question_id": <same as the mapped_id>
            
            new_data = {
                "answer": "",
                "section_id": row.get('section_id'),
                "language": row.get('language'),
                "subject_id": "123456789012",
                "subject": row.get('subject'),
                "grade_id": "123456789012",
                "grade": row.get('grade'),
                "country": row.get('country'),
                "question_id": str(mapped_id) # Cast to string to consistent with other ID fields
            }

            # Update json_data (root level)
            json_data.update(new_data)

            # Save
            save_json_file(json_data, target_dir / filepath.name)
            print(f"Processed {filepath.name} -> {category}/")

        except ValidationError as ve:
            print(f"Validation error in {filepath.name}: {ve}")
        except Exception as e:
            print(f"Error processing {filepath.name}: {e}")

if __name__ == '__main__':
    main()
