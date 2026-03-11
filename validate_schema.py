import app.models
from sqlmodel import SQLModel
from sqlalchemy import create_mock_engine

def dump(sql, *multiparams, **params):
    pass

engine = create_mock_engine("postgresql://", dump)

print("Starting SQLModel schema validation...")
try:
    SQLModel.metadata.create_all(engine)
    print("Schema validation successful!")
except Exception as e:
    print(f"Schema validation failed: {e}")
    import traceback
    traceback.print_exc()
