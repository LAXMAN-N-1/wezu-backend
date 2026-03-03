import os
import re

schemas = set()
for root, _, files in os.walk('app/models'):
    for file in files:
        if file.endswith('.py'):
            with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                for line in f:
                    match = re.search(r'"schema":\s*"([^"]+)"', line)
                    if match:
                        schemas.add(match.group(1))

for s in sorted(list(schemas)):
    print(s)
