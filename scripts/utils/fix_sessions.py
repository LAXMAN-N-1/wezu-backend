import os
import re

# Base directory for the app
base_dir = r"c:\Users\kamboja Srilaxmi\OneDrive\Desktop\wezu\wezu-backend\app"

def fix_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Could not read {filepath}: {e}")
        return

    changed = False
    new_content = content

    # 1. Standardize get_session to deps.get_db or get_db
    if 'get_session' in new_content:
        # Remove import
        new_content = re.sub(r'from app\.db\.session import get_session\n?', '', new_content)
        
        # Replace Depends(get_session) with Depends(deps.get_db) if it looks like an API route
        if 'api' in filepath:
             new_content = re.sub(r'Depends\(get_session\)', 'Depends(deps.get_db)', new_content)
        else:
             new_content = re.sub(r'Depends\(get_session\)', 'Depends(get_db)', new_content)
             if 'get_db' not in new_content:
                 if 'from app.core.database import' in new_content:
                     new_content = re.sub(r'(from app\.core\.database import [^\n]+)', r'\1, get_db', new_content)
                 else:
                     new_content = "from app.core.database import get_db\n" + new_content
        changed = True

    # 2. Ensure 'from app.api import deps' is present if 'deps.get_db' is used
    if 'deps.get_db' in new_content and 'from app.api import deps' not in new_content and 'import app.api.deps as deps' not in new_content:
        lines = new_content.splitlines()
        insert_idx = -1
        for i, line in enumerate(lines):
            if 'from app' in line or 'import app' in line:
                insert_idx = i + 1
        
        if insert_idx == -1:
             for i, line in enumerate(lines):
                 if line.startswith('from ') or line.startswith('import '):
                     insert_idx = i + 1
        
        if insert_idx != -1:
            lines.insert(insert_idx, 'from app.api import deps')
            new_content = '\n'.join(lines)
            changed = True

    if changed and new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed: {filepath}")

# Directories to scan
scan_dirs = [
    os.path.join(base_dir, 'api'),
    os.path.join(base_dir, 'services'),
]

for d in scan_dirs:
    for root, dirs, files in os.walk(d):
        for file in files:
            if file.endswith(".py"):
                fix_file(os.path.join(root, file))
