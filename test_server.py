import subprocess
import time
import requests
import sys

def main():
    # Start the server
    p = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8001"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    time.sleep(10) # wait for startup (startup took a few seconds in previous logs)
    
    try:
        r = requests.get("http://127.0.0.1:8001/api/v1/openapi.json")
        print(f"Status: {r.status_code}")
        print(f"Body: {r.text[:200]}")
    except Exception as e:
        print(f"Request failed: {e}")
        
    p.terminate()
    stdout, stderr = p.communicate()
    print("STDOUT:")
    print(stdout)
    print("STDERR:")
    print(stderr)

if __name__ == "__main__":
    main()
