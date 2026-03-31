"""
Fix UTC imports across all model files.
Replaces `from datetime import datetime` with `from datetime import datetime, UTC`
in files that use `datetime.now(UTC)` but don't import UTC.
"""
import os
import re

def fix_utc_imports():
    models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "models")
    fixed = []
    skipped = []
    
    for filename in sorted(os.listdir(models_dir)):
        if not filename.endswith(".py") or filename == "__init__.py":
            continue
        
        filepath = os.path.join(models_dir, filename)
        with open(filepath, "r") as f:
            content = f.read()
        
        # Skip if file doesn't use UTC at all
        if "UTC" not in content:
            skipped.append(f"{filename} (no UTC usage)")
            continue
        
        # Skip if already has UTC import
        if re.search(r"from datetime import.*\bUTC\b", content):
            skipped.append(f"{filename} (already has UTC)")
            continue
        
        # Fix: Replace `from datetime import datetime` with `from datetime import datetime, UTC`
        # Handle various forms:
        # 1. `from datetime import datetime`
        # 2. `from datetime import datetime, timedelta`
        # 3. `from datetime import datetime, timedelta, date`
        
        new_content = re.sub(
            r"from datetime import datetime\b(?!.*UTC)",
            "from datetime import datetime, UTC",
            content
        )
        
        if new_content != content:
            with open(filepath, "w") as f:
                f.write(new_content)
            fixed.append(filename)
        else:
            skipped.append(f"{filename} (no matching pattern)")
    
    print(f"\n{'='*60}")
    print(f"UTC Import Fix Summary")
    print(f"{'='*60}")
    print(f"Fixed: {len(fixed)} files")
    for f in fixed:
        print(f"  ✅ {f}")
    print(f"\nSkipped: {len(skipped)} files")
    for s in skipped:
        print(f"  ⏭️  {s}")
    print(f"{'='*60}")

if __name__ == "__main__":
    fix_utc_imports()
