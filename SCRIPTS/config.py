"""Configuration file for JSON conversion tool."""

LANGUAGES = {
    "en": "English",
    "ar": "Arabic",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "zh": "Chinese"
}

# Country code to country name mapping
COUNTRIES = {
    "eg": "Egypt",
    "zz": "ZZ"
}

# Valid question part types
VALID_PART_TYPES = [
    "mcq",
    "gmrq",
    "mrq",
    "frq",
    "oq",
    "gapText",
    "string",
    "opinion",
    "matching",
    "counting",
    "puzzle",
    "input_box",
    "frq_ai"
]

# Valid directions for ordering questions
VALID_DIRECTIONS = ["vertical", "horizontal"]

# Valid choice types
VALID_CHOICE_TYPES = ["key", "distractor"]

# Valid constraint types for input_box
VALID_CONSTRAINT_TYPES = ["decimal", "integer", "currencyValue"]

# Default source value
DEFAULT_SOURCE = "human"

# Grid size pattern for counting questions
GRID_SIZE_PATTERN = r'^\d+×\d+$'

# Error types for reporting
ERROR_TYPES = {
    "PRE_VALIDATION": "Pre-Conversion Validation",
    "CONVERSION": "Conversion",
    "POST_VALIDATION": "Post-Conversion Validation"
}

# Excel report columns
EXCEL_COLUMNS = [
    "Filename",
    "Question ID",
    "Error Type",
    "Error Message",
    "Failed Field",
    "Actual Value",
    "Expected Format",
    "Timestamp"
]