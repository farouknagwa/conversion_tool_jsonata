
import json
from pathlib import Path
from typing import Dict, Any, Union, List
from bs4 import BeautifulSoup

class ValidationError(Exception):
    def __init__(self, message, error_type, file_name, expected_format):
        super().__init__(message)
        self.error_type = error_type
        self.file_name = file_name
        self.expected_format = expected_format

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

def clean_html_attributes(data: Union[Dict, List, str, Any]) -> Union[Dict, List, str, Any]:
    """
    Recursively traverses the data structure.
    If a string is found, it attempts to parse it as HTML.
    If <p> tags are found, all attributes are removed from them.
    """
    if isinstance(data, dict):
        return {k: clean_html_attributes(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_html_attributes(item) for item in data]
    elif isinstance(data, str):
        # Optimization: check if it looks like HTML before parsing
        if "<p" in data: 
            try:
                soup = BeautifulSoup(data, 'html.parser')
                p_tags = soup.find_all('p')
                if p_tags:
                    changed = False
                    for p in p_tags:
                        if p.attrs:
                            p.attrs = {}
                            changed = True
                    if changed:
                         # str(soup) might return '<html><body>...</body></html>' if it added them.
                         # Generally for fragments it doesn't, but let's be careful.
                         # If the input didn't have <html>, we probably don't want it in output.
                         # For simple fragments, str(soup) is usually fine.
                        return str(soup)
            except Exception:
                # If parsing fails, return original string
                pass
        return data
    else:
        return data

def main():
    input_dir = Path("inputs")
    output_dir = Path("outputs")
    
    if not input_dir.exists():
        print(f"Input directory '{input_dir}' does not exist.")
        return

    json_files = list(input_dir.rglob("*.json"))
    if not json_files:
        print(f"No JSON files found in '{input_dir}'")
        return

    print(f"Found {len(json_files)} JSON files to process.")

    for json_file in json_files:
        try:
            data = load_json_file(json_file)
            cleaned_data = clean_html_attributes(data)
            
            # Preserve directory structure
            relative_path = json_file.relative_to(input_dir)
            output_path = output_dir / relative_path
            
            save_json_file(cleaned_data, output_path)
            print(f"Processed: {relative_path}")
            
        except ValidationError as e:
            print(f"Error processing {json_file.name}: {e}")
        except Exception as e:
            print(f"Unexpected error processing {json_file.name}: {e}")

if __name__ == "__main__":
    main()
