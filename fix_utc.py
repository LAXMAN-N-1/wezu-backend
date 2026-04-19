import os
import re

def fix_utc_imports(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r") as f:
                    content = f.read()
                
                modified = False
                
                # First, fix the broken lines I created in the last pass
                # Pattern: from datetime import timezone; UTC = timezone.utc, datetime
                if "from datetime import timezone; UTC = timezone.utc, datetime" in content:
                    content = content.replace("from datetime import timezone; UTC = timezone.utc, datetime", "from datetime import datetime, timezone; UTC = timezone.utc")
                    modified = True
                
                # Fix another possible broken variant
                if "from datetime import timezone; UTC = timezone.utc, datetim" in content:
                     content = content.replace("from datetime import timezone; UTC = timezone.utc, datetim", "from datetime import datetime, timezone; UTC = timezone.utc")
                     modified = True

                # General refactor with better regex
                # We want to match 'from datetime import ... UTC ...'
                # and replace it with 'from datetime import ... timezone; UTC = timezone.utc'
                # taking care of datetime itself.
                
                def replace_func(match):
                    imports_str = match.group(1)
                    imports = [i.strip() for i in imports_str.split(",")]
                    
                    has_utc = "UTC" in imports
                    if not has_utc:
                        return match.group(0)
                        
                    imports.remove("UTC")
                    if "timezone" not in imports:
                        imports.append("timezone")
                        
                    new_imports = ", ".join([i for i in imports if i])
                    return f"from datetime import {new_imports}; UTC = timezone.utc"

                # Match 'from datetime import [any list containing UTC]'
                new_content = re.sub(r"from datetime import ([\w\s,]+)\n?", replace_func, content)
                if new_content != content:
                    content = new_content
                    modified = True

                if modified:
                    with open(path, "w") as f:
                        f.write(content)
                    print(f"Fixed: {path}")

if __name__ == "__main__":
    fix_utc_imports("app")
