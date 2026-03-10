import os
import re

endpoints_md_path = "backend_endpoints.md"
v1_dir = "backend/app/api/v1"

with open(endpoints_md_path, "r") as f:
    endpoints_md = f.read()

# Extract endpoints from markdown
# format: - **METHOD** `/path` - description
expected_routes = []
current_prefix = ""
for line in endpoints_md.split("\n"):
    if line.startswith("### "):
        # e.g. ### 1. Authentication (`/auth`)
        m = re.search(r'\(`(/[^`]+)`\)', line)
        if m:
            current_prefix = m.group(1)
    elif line.startswith("-   **") or line.startswith("- **"):
        m = re.search(r'\*\*([A-Z]+)\*\* `([^`]+)`', line)
        if m:
            method = m.group(1)
            path = m.group(2)
            if path == "/":
                full_path = current_prefix
            else:
                full_path = current_prefix + path
            expected_routes.append({"method": method, "path": full_path, "prefix": current_prefix})

implemented_routes = []
for filename in os.listdir(v1_dir):
    if filename.endswith(".py") and filename != "__init__.py":
        filepath = os.path.join(v1_dir, filename)
        with open(filepath, "r") as f:
            content = f.read()
            # find @router.api_route or @router.get/post etc.
            matches = re.finditer(r'@router\.(get|post|put|delete|patch)\("([^"]+)"', content)
            for m in matches:
                method = m.group(1).upper()
                path = m.group(2)
                # We don't have the router prefix here easily without looking at main.py, 
                # but we can guess from filename or just collect them
                implemented_routes.append({"method": method, "path": path, "file": filename})

# Print out expected vs implemented to see what's missing
print("Expected Routes count:", len(expected_routes))
print("Implemented Routes count:", len(implemented_routes))

# To match, we need prefixes. Let's parse main.py or api.py to get prefixes
api_router_file = "backend/app/api/v1/__init__.py"
if not os.path.exists(api_router_file):
    api_router_file = "backend/app/main.py" # check where router is included

prefixes = {}
if os.path.exists(api_router_file):
    with open(api_router_file, "r") as f:
        pass # simplified for now
        
# For simplicity, let's just group implemented by file and manually map file to prefix
file_to_prefix = {
    "auth.py": "/auth",
    "users.py": "/users",
    "kyc.py": "/kyc",
    "stations.py": "/stations",
    "rentals.py": "/rentals",
    "wallet.py": "/wallet",
    "payments.py": "/payments",
    "batteries.py": "/batteries",
    "swaps.py": "/swaps",
    "iot.py": "/iot",
    "support.py": "/support",
    "notifications.py": "/notifications",
    "favorites.py": "/favorites",
    "analytics.py": "/analytics",
    "fraud.py": "/fraud"
}

normalized_implemented = []
for r in implemented_routes:
    prefix = file_to_prefix.get(r["file"], "")
    path = r["path"]
    if path == "/":
        full_path = prefix
    else:
        # Avoid double slashes
        if prefix.endswith("/") and path.startswith("/"):
            full_path = prefix + path[1:]
        elif not prefix.endswith("/") and not path.startswith("/"):
            full_path = prefix + "/" + path
        else:
            full_path = prefix + path
    normalized_implemented.append(f"{r['method']} {full_path}")

print("\nMissing Endpoints (Expected but not found):")
for ex in expected_routes:
    # Some paths have {id} vs {station_id} so path matching might be fuzzy.
    # Let's do a strict match first.
    ex_str = f"{ex['method']} {ex['path']}"
    # Replace parameter names with a generic regex or just string match
    found = False
    
    # Simple check
    # Convert {param} to something we can match, or just lowercase compare
    ex_path_normalized = re.sub(r'\{[^}]+\}', '{}', ex['path'])
    
    for imp in normalized_implemented:
        imp_path_normalized = re.sub(r'\{[^}]+\}', '{}', imp.split(" ")[1])
        if ex['method'] == imp.split(" ")[0] and ex_path_normalized == imp_path_normalized:
            found = True
            break
            
    if not found:
        print(f"- {ex['method']} {ex['path']}")

