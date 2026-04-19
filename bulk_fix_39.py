import os
import re

def fix_utc_line(line):
    if "from datetime import" in line and "UTC" in line:
        parts = line.split("import")
        prefix = parts[0] + "import "
        suffix = parts[1].split("#")[0].strip()
        comment = parts[1].split("#")[1] if "#" in parts[1] else ""
        
        imports = [i.strip() for i in suffix.split(",")]
        if "UTC" in imports:
            imports = [i for i in imports if i != "UTC"]
            if "timezone" not in imports:
                imports.append("timezone")
            
            new_line = prefix + ", ".join(imports) + "; UTC = timezone.utc"
            if comment:
                new_line += " #" + comment
            new_line += "\n"
            return new_line
    return line

def fix_file(path):
    with open(path, "r") as f:
        lines = f.readlines()
    
    modified = False
    new_lines = []
    
    # Check if annotations are already there
    has_annotations = any("from __future__ import annotations" in line for line in lines)
    if not has_annotations:
        # Avoid adding it to empty or non-python looking files
        new_lines.append("from __future__ import annotations\n")
        modified = True
    
    for line in lines:
        nl = fix_utc_line(line)
        if nl != line:
            modified = True
        new_lines.append(nl)
        
    if modified:
        with open(path, "w") as f:
            f.writelines(new_lines)
        return True
    return False

def main():
    count = 0
    for root, dirs, files in os.walk("app"):
        for file in files:
            if file.endswith(".py"):
                if fix_file(os.path.join(root, file)):
                    count += 1
    print(f"Fixed {count} files.")

if __name__ == "__main__":
    main()
