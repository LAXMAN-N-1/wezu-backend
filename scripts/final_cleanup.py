import os
import re

def fix_file_content(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Datetime migration
    # Replace datetime.utcnow() with datetime.now(UTC)
    content = content.replace('datetime.utcnow()', 'datetime.now(UTC)')
    # Replace default_factory=datetime.utcnow
    content = content.replace('default_factory=datetime.utcnow', 'default_factory=lambda: datetime.now(UTC)')
    # Replace default=datetime.utcnow
    content = content.replace('default=datetime.utcnow', 'default=lambda: datetime.now(UTC)')
    
    # Ensure UTC is imported if needed
    if 'datetime.now(UTC)' in content or 'lambda: datetime.now(UTC)' in content:
        if 'from datetime' in content and 'UTC' not in content:
            content = content.replace('from datetime import', 'from datetime import UTC,')
            # Clean up potential double commas
            content = content.replace('import UTC,,', 'import UTC,')
            content = content.replace('import , UTC', 'import UTC')

    # 2. SQLModel Query migration (Simple cases)
    # session.query(User).filter(...) -> session.exec(select(User).where(...))
    # This is harder with regex, but we can catch simple ones
    # content = re.sub(r'(db|session|self\.db)\.query\((.*?)\)\.filter\((.*?)\)\.first\(\)', r'\1.exec(select(\2).where(\3)).first()', content)
    # content = re.sub(r'(db|session|self\.db)\.query\((.*?)\)\.filter\((.*?)\)\.all\(\)', r'\1.exec(select(\2).where(\3)).all()', content)
    
    # Actually, let's just do the ones we found in grep manually or with targeted regex
    if 'rbac_middleware.py' in file_path:
        content = content.replace('db.query(User).filter(User.id == int(token_data.sub)).options(selectinload(User.role)).first()', 
                                  'db.exec(select(User).where(User.id == int(token_data.sub)).options(selectinload(User.role))).first()')
        if 'from sqlmodel import' in content and 'select' not in content:
            content = content.replace('from sqlmodel import', 'from sqlmodel import select,')

    if 'app/core/audit.py' in file_path:
         content = content.replace('db.query(AuditLog).filter(AuditLog.timestamp < cutoff).delete()',
                                   'db.execute(delete(AuditLog).where(AuditLog.timestamp < cutoff))')
         if 'from sqlmodel import' in content and 'delete' not in content:
             content = content.replace('from sqlmodel import', 'from sqlmodel import delete,')

    with open(file_path, 'w') as f:
        f.write(content)

def main():
    for root, dirs, files in os.walk('app'):
        for file in files:
            if file.endswith('.py'):
                fix_file_content(os.path.join(root, file))
    
    # Also check tests/
    for root, dirs, files in os.walk('tests'):
        for file in files:
            if file.endswith('.py'):
                fix_file_content(os.path.join(root, file))

if __name__ == "__main__":
    main()
