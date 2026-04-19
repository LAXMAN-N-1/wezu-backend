import os

def fix_utc_line(line):
    if "from datetime import" in line and "UTC" in line:
        # Simple line-based replacement
        if "datetime" in line:
            # Handle from datetime import datetime, UTC
            # or from datetime import UTC, datetime
            # or from datetime import date, datetime, UTC
            line = line.replace("UTC", "timezone").strip()
            if "timezone" not in line: # safeguard
                 line += ", timezone"
            line = line.rstrip(",") + "; UTC = timezone.utc\n"
            return line
        else:
            # Handle from datetime import UTC
            line = line.replace("UTC", "timezone").strip()
            line = line.rstrip(",") + "; UTC = timezone.utc\n"
            return line
    return line

def fix_utc_imports(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r") as f:
                    lines = f.readlines()
                
                new_lines = []
                modified = False
                for line in lines:
                    if "from datetime import" in line and "UTC" in line:
                        # Better handling for list of imports
                        parts = line.split("import")
                        prefix = parts[0] + "import "
                        suffix = parts[1].split("#")[0].strip() # remove comments for parsing
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
                            
                            new_lines.append(new_line)
                            modified = True
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)
                
                if modified:
                    with open(path, "w") as f:
                        f.writelines(new_lines)
                    print(f"Fixed: {path}")

if __name__ == "__main__":
    fix_utc_imports("app")
