import os
import re

d = 'alembic/versions'
for f in os.listdir(d):
    if not f.endswith('.py'): continue
    path = os.path.join(d, f)
    with open(path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    orig = content
    # Remove schema='...' kwargs in SQLAlchemy calls
    content = re.sub(r",\s*schema=['\"][a-zA-Z0-9_]+['\"]", "", content)
    content = re.sub(r"schema=['\"][a-zA-Z0-9_]+['\"]\s*,\s*", "", content)
    
    # Replace schema.table references in strings ('core.users')
    content = re.sub(r"['\"](?:core|inventory|dealer|logistics|finance|public)\.([a-zA-Z0-9_]+)['\"]", r"'\1'", content)
    
    # Replace schema.table.column in Foreign keys ('core.users.id')
    content = re.sub(r"['\"](?:core|inventory|dealer|logistics|finance|public)\.([a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)['\"]", r"'\1'", content)
    
    # Replace schema.table references in raw SQL like ALTER TABLE core.users
    content = re.sub(r"(?:TABLE|table)\s+(?:core|inventory|dealer|logistics|finance|public)\.([a-zA-Z0-9_]+)", r"TABLE \1", content)
    
    if orig != content:
        with open(path, 'w', encoding='utf-8') as file:
            file.write(content)
        print(f"Fixed {f}")
