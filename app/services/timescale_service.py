"""
TimescaleDB Service
Time-series data management for IoT and analytics
"""
from sqlalchemy import create_engine, text
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class TimescaleDBService:
    """TimescaleDB integration for time-series data"""
    
    def __init__(self):
        # Use same database but with TimescaleDB extension
        self.engine = create_engine(settings.DATABASE_URL)
    
    def setup_hypertables(self):
        """
        Setup TimescaleDB hypertables for time-series data
        Converts regular tables to hypertables for better performance
        """
        try:
            with self.engine.connect() as conn:
                # Enable TimescaleDB extension
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
                
                # Convert telemetry to hypertable in inventory schema
                conn.execute(text("""
                    SELECT create_hypertable(
                        'inventory.telemetry',
                        'timestamp',
                        if_not_exists => TRUE,
                        chunk_time_interval => INTERVAL '1 day'
                    );
                """))
                
                # Convert gps_tracking_log to hypertable
                conn.execute(text("""
                    SELECT create_hypertable(
                        'gps_tracking_log',
                        'timestamp',
                        if_not_exists => TRUE,
                        chunk_time_interval => INTERVAL '1 day'
                    );
                """))
                
                # Convert transactions to hypertable
                conn.execute(text("""
                    SELECT create_hypertable(
                        'transactions',
                        'created_at',
                        if_not_exists => TRUE,
                        chunk_time_interval => INTERVAL '7 days'
                    );
                """))
                
                conn.commit()
                logger.info("TimescaleDB hypertables created successfully")
                
        except Exception as e:
            logger.error(f"Failed to setup hypertables: {str(e)}")
    
    def setup_compression(self):
        """Setup automatic compression for old data"""
        try:
            with self.engine.connect() as conn:
                # Compress telemetry logs older than 7 days
                conn.execute(text("""
                    ALTER TABLE inventory.telemetry SET (
                        timescaledb.compress,
                        timescaledb.compress_segmentby = 'battery_id'
                    );
                """))
                
                conn.execute(text("""
                    SELECT add_compression_policy(
                        'inventory.telemetry',
                        INTERVAL '7 days',
                        if_not_exists => TRUE
                    );
                """))
                
                # Compress GPS logs older than 7 days
                conn.execute(text("""
                    ALTER TABLE gps_tracking_log SET (
                        timescaledb.compress,
                        timescaledb.compress_segmentby = 'rental_id'
                    );
                """))
                
                conn.execute(text("""
                    SELECT add_compression_policy(
                        'gps_tracking_log',
                        INTERVAL '7 days',
                        if_not_exists => TRUE
                    );
                """))
                
                conn.commit()
                logger.info("Compression policies created successfully")
                
        except Exception as e:
            logger.error(f"Failed to setup compression: {str(e)}")
    
    def setup_retention_policies(self):
        """Setup data retention policies"""
        try:
            with self.engine.connect() as conn:
                # Retain telemetry logs for 90 days
                conn.execute(text("""
                    SELECT add_retention_policy(
                        'inventory.telemetry',
                        INTERVAL '90 days',
                        if_not_exists => TRUE
                    );
                """))
                
                # Retain GPS logs for 60 days
                conn.execute(text("""
                    SELECT add_retention_policy(
                        'gps_tracking_log',
                        INTERVAL '60 days',
                        if_not_exists => TRUE
                    );
                """))
                
                conn.commit()
                logger.info("Retention policies created successfully")
                
        except Exception as e:
            logger.error(f"Failed to setup retention policies: {str(e)}")
    
    def get_battery_health_timeseries(
        self,
        battery_id: int,
        start_time: datetime,
        end_time: datetime,
        interval: str = '1 hour'
    ) -> List[Dict]:
        """
        Get aggregated battery health data
        
        Args:
            battery_id: Battery ID
            start_time: Start time
            end_time: End time
            interval: Aggregation interval (e.g., '1 hour', '1 day')
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(f"""
                    SELECT
                        time_bucket(:interval, timestamp) AS bucket,
                        AVG(voltage) as avg_voltage,
                        AVG(current) as avg_current,
                        AVG(temperature) as avg_temperature,
                        AVG(soc) as avg_soc,
                        AVG(soh) as avg_health
                    FROM inventory.telemetry
                    WHERE battery_id = :battery_id
                        AND timestamp >= :start_time
                        AND timestamp <= :end_time
                    GROUP BY bucket
                    ORDER BY bucket;
                """), {
                    'interval': interval,
                    'battery_id': battery_id,
                    'start_time': start_time,
                    'end_time': end_time
                })
                
                return [
                    {
                        'timestamp': row[0].isoformat(),
                        'avg_voltage': float(row[1]) if row[1] else None,
                        'avg_current': float(row[2]) if row[2] else None,
                        'avg_temperature': float(row[3]) if row[3] else None,
                        'avg_soc': float(row[4]) if row[4] else None,
                        'avg_health': float(row[5]) if row[5] else None
                    }
                    for row in result
                ]
                
        except Exception as e:
            logger.error(f"Failed to get battery health timeseries: {str(e)}")
            return []
    
    def get_realtime_analytics(self) -> Dict:
        """Get real-time system analytics"""
        try:
            with self.engine.connect() as conn:
                # Active rentals
                active_rentals = conn.execute(text("""
                    SELECT COUNT(*) FROM rentals WHERE status = 'active';
                """)).scalar()
                
                # Batteries in use
                batteries_in_use = conn.execute(text("""
                    SELECT COUNT(*) FROM batteries WHERE status = 'rented';
                """)).scalar()
                
                # Revenue today
                today_revenue = conn.execute(text("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM transactions
                    WHERE status = 'SUCCESS'
                        AND created_at >= CURRENT_DATE;
                """)).scalar()
                
                # Average battery health
                avg_health = conn.execute(text("""
                    SELECT AVG(health_percentage)
                    FROM batteries
                    WHERE status IN ('available', 'rented');
                """)).scalar()
                
                return {
                    'active_rentals': active_rentals,
                    'batteries_in_use': batteries_in_use,
                    'revenue_today': float(today_revenue),
                    'avg_battery_health': float(avg_health) if avg_health else 0
                }
                
        except Exception as e:
            logger.error(f"Failed to get real-time analytics: {str(e)}")
            return {}


# Global instance
timescale_service = TimescaleDBService()
