import os
import re

def fix_config_dict_imports(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if not file.endswith(".py"):
                continue
            
            path = os.path.join(root, file)
            with open(path, "r") as f:
                content = f.read()
            
            # Check if ConfigDict is used but not imported
            if "ConfigDict" in content and "from pydantic import" in content and "ConfigDict" not in content:
                # Add to existing pydantic import
                new_content = re.sub(r"from pydantic import (.*)", r"from pydantic import ConfigDict, \1", content)
                # Clean up double commas or extra spaces if they occur
                new_content = new_content.replace("ConfigDict, ConfigDict", "ConfigDict")
                
                if new_content != content:
                    with open(path, "w") as f:
                        f.write(new_content)
                    print(f"Fixed import in {path}")
            
            elif "ConfigDict" in content and "from pydantic" not in content and "import pydantic" not in content:
                # Add new import if pydantic isn't imported at all
                new_content = "from pydantic import ConfigDict\n" + content
                with open(path, "w") as f:
                    f.write(new_content)
                print(f"Added new import to {path}")

if __name__ == "__main__":
    fix_config_dict_imports("app")
    fix_config_dict_imports("tests")
