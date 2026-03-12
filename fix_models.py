import os
import re

models_dir = "app/models"

def fix_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Pattern 1: __table_args__ = {# "schema": "aligned_to_public"}
    # Should become # __table_args__ = {"schema": "public"}
    content = re.sub(r'__table_args__ = \{# "schema": "aligned_to_public"\}', '# __table_args__ = {"schema": "public"}', content)

    # Pattern 2: {# "schema": "aligned_to_public"} inside a tuple
    # Should just be removed (and handle trailing/leading commas)
    content = re.sub(r',\s*\{# "schema": "aligned_to_public"\}', '', content)
    content = re.sub(r'\{# "schema": "aligned_to_public"\},\s*', '', content)
    content = re.sub(r'\{# "schema": "aligned_to_public"\}', '', content)

    # Pattern 3: Broader match for any remaining broken schema comments
    content = re.sub(r'# "schema": "aligned_to_public"', '"schema": "public"', content)
    
    # Fix any double comments if they occurred
    content = re.sub(r'# #', '#', content)

    with open(filepath, 'w') as f:
        f.write(content)

for root, dirs, files in os.walk(models_dir):
    for file in files:
        if file.endswith(".py"):
            fix_file(os.path.join(root, file))
