import os
import re

tests_dir = 'tests'

for root, _, files in os.walk(tests_dir):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            original = content
            
            content = content.replace('kyc_status="verified"', 'kyc_status="approved"')
            content = content.replace("kyc_status='verified'", "kyc_status='approved'")
            
            # Replace Enum error strings
            content = content.replace('status="verified"', 'status="verified"') # Keep document status verified
            
            def inject_phone(m):
                inner = m.group(2)
                prefix = m.group(1)
                if 'phone_number' in inner:
                    return m.group(0)
                import uuid
                new_phone = str(uuid.uuid4().int)[:10]
                return f"{prefix}phone_number='{new_phone}', {inner})"
            
            content = re.sub(r'(\b(?:Admin)?User\s*\()([^)]*)\)', inject_phone, content, flags=re.DOTALL)
            
            if content != original:
                if 'import uuid' not in content:
                    content = 'import uuid\n' + content
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Updated {filepath}")
