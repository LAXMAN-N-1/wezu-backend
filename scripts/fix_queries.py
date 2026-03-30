import os
import re

def fix_query_to_exec(content):
    if 'db.query' in content or 'session.query' in content or 'self.session.query' in content:
        # Add select, func to imports if needed
        if 'from sqlmodel import' in content:
            for word in ['select', 'func']:
                if word not in content:
                    content = content.replace('from sqlmodel import ', f'from sqlmodel import {word}, ')
        
        # 1. Simple first()
        # db.query(User).filter(User.id == x).first() -> db.exec(select(User).where(User.id == x)).first()
        content = re.sub(r'(db|session|self\.session)\.query\((\w+)\)\.filter\(([^)]+)\)\.first\(\)', 
                         r'\1.exec(select(\2).where(\3)).first()', content)
        
        # 2. Simple scalar/one
        # db.query(func.count(User.id)).scalar() -> db.exec(select(func.count(User.id))).one()
        content = re.sub(r'(db|session|self\.session)\.query\(func\.count\(([^)]+)\)\)\.scalar\(\)', 
                         r'\1.exec(select(func.count(\2))).one()', content)
        
        # 3. Simple all()
        content = re.sub(r'(db|session|self\.session)\.query\((\w+)\)\.all\(\)', 
                         r'\1.exec(select(\2)).all()', content)

        # 4. Filter with options (selectinload)
        # db.query(User).filter(User.id == x).options(selectinload(User.role)).first()
        content = re.sub(r'(db|session|self\.session)\.query\((\w+)\)\.filter\(([^)]+)\)\.options\(([^)]+)\)\.first\(\)', 
                         r'\1.exec(select(\2).where(\3).options(\4)).first()', content)

    return content

def process_files(directory):
    for root, dirs, files in os.walk(directory):
        if '__pycache__' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                with open(path, 'r') as f:
                    content = f.read()
                
                original = content
                content = fix_query_to_exec(content)
                
                if content != original:
                    with open(path, 'w') as f:
                        f.write(content)
                    print(f"Fixed Query: {path}")

if __name__ == '__main__':
    process_files('app')
