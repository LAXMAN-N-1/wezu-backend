
import os
import re

SCHEMAS_DIR = "/Users/mohithavala/.gemini/antigravity/scratch/wezu-backend/app/schemas"

def migrate_file(filepath):
    with open(filepath, "r") as f:
        content = f.read()

    if "class Config:" not in content and "orm_mode" not in content and "from_attributes" not in content:
        return

    print(f"Migrating {filepath}...")

    # 1. Add ConfigDict import
    if "ConfigDict" not in content:
        if "from pydantic import" in content:
            content = re.sub(r"from pydantic import (.*)", r"from pydantic import \1, ConfigDict", content)
            # Cleanup double commas or spaces if any (naive approach usually works for simple imports)
            content = content.replace(",,", ",")
        else:
            # Add new import line
            content = "from pydantic import ConfigDict\n" + content

    # 2. regex replace class Config block
    # Pattern: class Config:\n\s+orm_mode = True
    # We want to replace it with model_config = ConfigDict(from_attributes=True)
    
    # Simple case: class Config: orm_mode = True (multiline)
    # We'll try to find the block and replace it.
    
    lines = content.splitlines()
    new_lines = []
    skip_count = 0
    
    for i, line in enumerate(lines):
        if skip_count > 0:
            skip_count -= 1
            continue
            
        stripped = line.strip()
        if stripped.startswith("class Config:"):
            # Check next line for orm_mode = True or from_attributes = True
            if i + 1 < len(lines):
                next_line = lines[i+1].strip()
                if "orm_mode = True" in next_line or "from_attributes = True" in next_line:
                    indent = line[:line.find("class")]
                    new_lines.append(f"{indent}model_config = ConfigDict(from_attributes=True)")
                    skip_count = 1 # Skip the next line
                    continue
        
        # Handle cases where `orm_mode = True` is might be lingering elsewhere or different formatting?
        # For now, let's stick to the common pattern seen in grep.
        
        new_lines.append(line)
        
    content = "\n".join(new_lines) + "\n" # Restore trailing newline
    
    with open(filepath, "w") as f:
        f.write(content)

def main():
    for filename in os.listdir(SCHEMAS_DIR):
        if filename.endswith(".py"):
            migrate_file(os.path.join(SCHEMAS_DIR, filename))

if __name__ == "__main__":
    main()
