import os
import re

def fix_utcnow(content):
    # Add UTC to imports if needed
    if 'datetime.utcnow()' in content:
        if 'from datetime import datetime' in content and 'UTC' not in content:
            content = content.replace('from datetime import datetime', 'from datetime import datetime, UTC')
        elif 'from datetime import datetime, timedelta' in content and 'UTC' not in content:
            content = content.replace('from datetime import datetime, timedelta', 'from datetime import datetime, timedelta, UTC')
        
        # Replace local imports within functions
        content = re.sub(r'( +)from datetime import datetime, timedelta\b(?!, UTC)', r'\1from datetime import datetime, timedelta, UTC', content)
        content = re.sub(r'( +)from datetime import datetime\b(?!, UTC)', r'\1from datetime import datetime, UTC', content)
        
        # Replace the call
        content = content.replace('datetime.utcnow()', 'datetime.now(UTC)')
    return content

def fix_orm_mode(content):
    if 'orm_mode = True' in content or 'from_attributes = True' in content:
        # Add ConfigDict to imports
        if 'from pydantic import' in content and 'ConfigDict' not in content:
            content = re.sub(r'from pydantic import ([\w, ]+)', r'from pydantic import \1, ConfigDict', content)
        
        # Replace class Config
        pattern = r'class Config:\s+(?:orm_mode|from_attributes) = True'
        content = re.sub(pattern, 'model_config = ConfigDict(from_attributes=True)', content)
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
                content = fix_utcnow(content)
                content = fix_orm_mode(content)
                
                if content != original:
                    with open(path, 'w') as f:
                        f.write(content)
                    print(f"Fixed: {path}")

if __name__ == '__main__':
    process_files('app')
    process_files('tests')
