import traceback
from fastapi.testclient import TestClient

def main():
    try:
        from app.main import app
        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/api/v1/openapi.json")
        print(f"Status: {response.status_code}")
        print(f"Text: {response.text[:500]}")
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    main()
