import os
import re

MARKER_MAP = {
    "tests/unit": "unit",
    "tests/integration": "integration",
    "tests/regression": "regression",
    "tests/test_smoke.py": "smoke"
}

def add_marker_to_file(filepath, marker):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove existing pytestmark lines to avoid duplicates/errors
    # Match "pytestmark = pytest.mark.xxx"
    content = re.sub(r'pytestmark\s*=\s*pytest\.mark\.\w+\s*', '', content)
    content = re.sub(r'import pytest\s*', '', content) # Remove top level import to re-add it cleanly
    
    # Strip leading whitespace/newlines
    content = content.lstrip()
    
    # Reconstruct file
    new_content = f"import pytest\npytestmark = pytest.mark.{marker}\n\n{content}"
    
    print(f"Fixing {filepath}")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

def main():
    root = os.getcwd()
    for path, marker in MARKER_MAP.items():
        full_path = os.path.join(root, path)
        if os.path.isfile(full_path):
            add_marker_to_file(full_path, marker)
        else:
            for root_dir, _, files in os.walk(full_path):
                for file in files:
                    if file.startswith("test_") and file.endswith(".py"):
                        add_marker_to_file(os.path.join(root_dir, file), marker)

if __name__ == "__main__":
    main()
