import time
print("Starting import...")
start = time.time()
try:
    import app.models
    print(f"Import app.models successful in {time.time() - start:.2f}s")
except Exception as e:
    print(f"Error importing app.models: {e}")

start = time.time()
try:
    from app.main import app
    print(f"Import app.main successful in {time.time() - start:.2f}s")
except Exception as e:
    print(f"Error importing app.main: {e}")
