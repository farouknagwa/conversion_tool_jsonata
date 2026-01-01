#!/usr/bin/env python3
"""
Distribute JSON files by question part type.

For single-part questions: Copies files to outputs/<parttype>/
For multipart questions: Copies files to outputs/multipart/
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, Tuple
from collections import defaultdict


def load_json_file(filepath: Path) -> Dict[str, Any]:
    """Load JSON file with error handling."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath.name}: {e}")
        return None


def determine_output_path(json_data: Dict[str, Any], filename: str, output_base: Path) -> Tuple[Path, str]:
    """
    Determine the output path based on question type.
    
    Returns:
        Tuple of (output_path, category_name)
    """
    if not json_data:
        return None, None
    
    number_of_parts = json_data.get('number_of_parts', 0)
    
    # Check for parts in content structure
    parts = json_data.get('content', {}).get('parts', [])
    if not parts:
        parts = json_data.get('parts', [])
    
    if not parts:
        print(f"Warning: {filename} has no parts, skipping...")
        return None, None
    
    # Multipart question
    if number_of_parts > 1 or len(parts) > 1:
        output_dir = output_base / 'multipart'
        return output_dir, 'multipart'
    
    # Single-part question
    if len(parts) > 0:
        part_type = parts[0].get('type')
        if not part_type:
            print(f"Warning: {filename} has part without type, skipping...")
            return None, None
        
        output_dir = output_base / part_type
        return output_dir, part_type
    
    print(f"Warning: {filename} has no valid parts, skipping...")
    return None, None


def distribute_files(input_dir: Path, output_base: Path, dry_run: bool = False):
    """
    Distribute JSON files from input_dir to output_base based on part type.
    
    Args:
        input_dir: Directory containing input JSON files
        output_base: Base directory for output subdirectories
        dry_run: If True, only show what would be done without copying files
    """
    if not input_dir.exists():
        print(f"Error: Input directory '{input_dir}' does not exist.")
        return
    
    json_files = list(input_dir.rglob("*.json"))
    
    if not json_files:
        print(f"No JSON files found in '{input_dir}'")
        return
    
    print(f"Found {len(json_files)} JSON files to process.")
    print(f"{'DRY RUN MODE - No files will be copied' if dry_run else ''}\n")
    
    stats = defaultdict(int)
    errors = []
    
    for json_file in json_files:
        try:
            json_data = load_json_file(json_file)
            if json_data is None:
                errors.append(json_file.name)
                continue
            
            output_dir, category = determine_output_path(json_data, json_file.name, output_base)
            
            if output_dir is None:
                errors.append(json_file.name)
                continue
            
            # Create output directory if it doesn't exist
            if not dry_run:
                output_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy file to appropriate directory
            output_path = output_dir / json_file.name
            
            if dry_run:
                print(f"Would copy: {json_file.name} → {output_path.relative_to(output_base)}")
            else:
                shutil.copy2(json_file, output_path)
                print(f"Copied: {json_file.name} → {category}/")
            
            stats[category] += 1
            
        except Exception as e:
            print(f"Error processing {json_file.name}: {e}")
            errors.append(json_file.name)
    
    # Print summary
    print("\n" + "=" * 80)
    print("DISTRIBUTION SUMMARY")
    print("=" * 80)
    print(f"Total files processed: {len(json_files)}")
    print(f"Successfully distributed: {sum(stats.values())}")
    print(f"Errors: {len(errors)}")
    
    if stats:
        print("\nFiles by category:")
        for category in sorted(stats.keys()):
            print(f"  {category}: {stats[category]}")
    
    if errors:
        print(f"\nFiles with errors ({len(errors)}):")
        for error_file in errors[:10]:  # Show first 10
            print(f"  - {error_file}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
    
    print("=" * 80)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Distribute JSON files by question part type',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Distribute files (actual copy)
  python distribute_by_type.py
  
  # Dry run (show what would be done)
  python distribute_by_type.py --dry-run
  
  # Custom input/output paths
  python distribute_by_type.py --input custom/inputs --output custom/outputs
        """
    )
    
    parser.add_argument('--input', '-i', type=str, default='inputs',
                       help='Input directory (default: inputs)')
    parser.add_argument('--output', '-o', type=str, default='outputs',
                       help='Output base directory (default: outputs)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without copying files')
    
    args = parser.parse_args()
    
    # Get script directory
    script_dir = Path(__file__).parent
    input_dir = (script_dir / args.input).resolve()
    output_base = (script_dir / args.output).resolve()
    
    distribute_files(input_dir, output_base, args.dry_run)


if __name__ == '__main__':
    main()

