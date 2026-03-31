import os

models_dir = os.path.join(os.path.dirname(__file__), '../app/models')

for filename in os.listdir(models_dir):
    if not filename.endswith('.py'):
        continue
    filepath = os.path.join(models_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    has_uuid_import = False
    needs_update = False
    
    for line in lines:
        if line.strip() == "import uuid":
            if not has_uuid_import:
                has_uuid_import = True
            else:
                needs_update = True # duplicate
        else:
            new_lines.append(line)
            
    if has_uuid_import:
        # Check if already at start
        if new_lines and not new_lines[0].startswith("import uuid"):
            new_lines.insert(0, "import uuid\n")
            needs_update = True
            
    if needs_update:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f"Fixed imports in {filename}")

print("Done fixing imports.")

