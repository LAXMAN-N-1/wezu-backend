import os
import re

models_dir = os.path.join(os.path.dirname(__file__), '../app/models')

for filename in os.listdir(models_dir):
    if not filename.endswith('.py'):
        continue
    filepath = os.path.join(models_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Look for battery_id: Optional[int] or int with foreign_key to inventory.batteries.id
    # We will use regex to find: `battery_id: (Optional\[)?int(\])? = Field(.*?foreign_key="inventory.batteries.id".*?)`
    
    pattern1 = r'([a-zA-Z_]+):\s*(?:Optional\[)?int(?:\])?\s*=\s*Field\((.*?foreign_key="inventory.batteries.id".*?)\)'
    
    def repl1(match):
        field_name = match.group(1)
        params = match.group(2)
        return f'{field_name}: Optional[uuid.UUID] = Field({params})'
        
    new_content, count = re.subn(pattern1, repl1, content)
    
    if count > 0:
        # add import uuid if missing
        if 'import uuid' not in new_content:
            new_content = 'import uuid\n' + new_content
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {count} fields in {filename}")

print("Done updating battery_id types in models.")

