from sqlmodel import Session, select, func, create_engine
from app.core.config import settings
from app.models.station import Station
from app.models.station_heartbeat import StationHeartbeat
from datetime import datetime, timedelta
from sqlalchemy import JSON, Float, cast

engine = create_engine(settings.DATABASE_URL)

def test_query():
    with Session(engine) as session:
        threshold_24h = datetime.utcnow() - timedelta(hours=24)
        print(f"Testing query with threshold: {threshold_24h}")
        
        try:
            # Test simple count
            count = session.exec(select(func.count(StationHeartbeat.id))).one()
            print(f"Total heartbeats: {count}")
            
            # Test complex avg latency query
            # We use SQLAlchemy's cast and JSON type for correctness
            # func.json_extract_path_text is a Postgres function
            stmt = select(
                func.avg(
                    cast(
                        func.json_extract_path_text(
                            cast(StationHeartbeat.metrics, JSON), 
                            'network_latency'
                        ), 
                        Float
                    )
                )
            ).where(StationHeartbeat.timestamp >= threshold_24h)
            
            avg_lat = session.exec(stmt).one()
            print(f"Average latency: {avg_lat}")
            
        except Exception as e:
            print(f"Error encountered: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_query()
