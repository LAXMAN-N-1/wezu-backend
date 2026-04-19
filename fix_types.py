import os
import re

def find_type_start(s, end_idx):
    brackets = 0
    # Search backwards for the most plausible start of the type hint
    for i in range(end_idx - 1, -1, -1):
        if s[i] == ']':
            brackets += 1
        elif s[i] == '[':
            brackets -= 1
        elif brackets == 0 and s[i] in ':(':
            return i + 1
        elif brackets == 0 and s[i] == ',':
            return i + 1
    return 0

def fix_content(content):
    modified = False
    lines = content.splitlines()
    new_lines = []
    
    for line in lines:
        if "|" in line:
            # Check if it looks like a type hint line
            if ":" in line or "->" in line:
                # Iterate through all | in the line
                i = line.find("|")
                while i != -1:
                    # Look for None on the right
                    tail = line[i+1:].lstrip()
                    is_optional = tail.lower().startswith("none")
                    
                    start = find_type_start(line, i)
                    
                    if is_optional:
                        # Find end of 'None'
                        none_match = re.search(r"none\b", line[i+1:], re.IGNORECASE)
                        if none_match:
                            end = i + 1 + none_match.end()
                            t1 = line[start:i].strip()
                            replacement = f"Optional[{t1}]"
                            line = line[:start] + replacement + line[end:]
                            modified = True
                            i = line.find("|", start + len(replacement))
                        else:
                            i = line.find("|", i + 1)
                    else:
                        # T1 | T2
                        end_match = re.search(r"[,=)\n#:]", line[i+1:])
                        end = i + 1 + end_match.start() if end_match else len(line)
                        
                        t1 = line[start:i].strip()
                        t2 = line[i+1:end].strip()
                        
                        if t1 and t2 and not any(c in t1+t2 for c in "+-*/%<>"): 
                            replacement = f"Union[{t1}, {t2}]"
                            line = line[:start] + replacement + line[end:]
                            modified = True
                            i = line.find("|", start + len(replacement))
                        else:
                            i = line.find("|", i + 1)
            else:
                pass # Not a type hint line or at least one we can safely fix
        new_lines.append(line)

    if modified:
        content = "\n".join(new_lines) + "\n"
        has_optional = "Optional[" in content
        has_union = "Union[" in content
        
        if has_optional or has_union:
            if "from typing import" in content:
                def add_typing(match):
                    imports = match.group(1)
                    if has_optional and "Optional" not in imports:
                        imports += ", Optional"
                    if has_union and "Union" not in imports:
                        imports += ", Union"
                    return f"from typing import {imports}"
                content = re.sub(r"from typing import ([\w, ]+)", add_typing, content)
            else:
                imports = []
                if has_optional: imports.append("Optional")
                if has_union: imports.append("Union")
                content = f"from typing import {', '.join(imports)}\n" + content
                
    return content, modified

def main():
    count = 0
    for root, dirs, files in os.walk("app"):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r") as f:
                    content = f.read()
                new_content, modified = fix_content(content)
                if modified:
                    with open(path, "w") as f:
                        f.write(new_content)
                    print(f"Fixed: {path}")
                    count += 1
    print(f"Total files fixed: {count}")

if __name__ == "__main__":
    main()
