import os
import glob

files = glob.glob("tests/api/v1/**/*.py", recursive=True)
for filepath in files:
    with open(filepath, "r") as f:
        content = f.read()
    
    if "dependency_overrides[deps.get_current_active_superuser]" in content:
        content = content.replace(
            "dependency_overrides[deps.get_current_active_superuser]", 
            "dependency_overrides[deps.get_current_active_admin]"
        )
        with open(filepath, "w") as f:
            f.write(content)

print("Dependencies fixed.")
