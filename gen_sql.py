import app.models.station_heartbeat
import app.models.alert
from sqlmodel import SQLModel, create_engine
from sqlalchemy import schema

engine = create_engine("postgresql://")

def get_sql():
    # Only for our two new tables
    tables = [SQLModel.metadata.tables["station_heartbeats"], SQLModel.metadata.tables["alerts"]]
    
    for table in tables:
        print(f"--- Table: {table.name} ---")
        print(str(schema.CreateTable(table).compile(engine)))
        for index in table.indexes:
            print(str(schema.CreateIndex(index).compile(engine)))

if __name__ == "__main__":
    get_sql()
