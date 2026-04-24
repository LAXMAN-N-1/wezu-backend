from __future__ import annotations
from typing import Dict, List, Any

# Master Dashboard Configuration
# Defines default widgets and layouts for different roles.

MASTER_DASHBOARD_CONFIG: Dict[str, List[Dict[str, Any]]] = {
    "admin": [
        {
            "id": "revenue_chart",
            "type": "chart",
            "title": "Total Revenue",
            "config": {"chart_type": "line", "data_source": "/api/v1/analytics/revenue"},
            "position": {"x": 0, "y": 0, "w": 8, "h": 4}
        },
        {
            "id": "active_users_stat",
            "type": "stat",
            "title": "Active Users",
            "config": {"data_source": "/api/v1/analytics/users/active"},
            "position": {"x": 8, "y": 0, "w": 4, "h": 2}
        },
        {
            "id": "battery_health_map",
            "type": "map",
            "title": "Battery Health Heatmap",
            "config": {"data_source": "/api/v1/batteries/map"},
            "position": {"x": 0, "y": 4, "w": 12, "h": 6}
        }
    ],
    "vendor_owner": [
        {
            "id": "station_status",
            "type": "list",
            "title": "Station Status",
            "config": {"data_source": "/api/v1/stations/status"},
            "position": {"x": 0, "y": 0, "w": 6, "h": 4}
        },
        {
            "id": "daily_swaps",
            "type": "chart",
            "title": "Daily Swaps",
            "config": {"chart_type": "bar", "data_source": "/api/v1/analytics/swaps/daily"},
            "position": {"x": 6, "y": 0, "w": 6, "h": 4}
        }
    ],
    "customer": [
        {
            "id": "vehicle_soc",
            "type": "stat",
            "title": "Vehicle State of Charge",
            "config": {"data_source": "/api/v1/vehicles/me/soc"},
            "position": {"x": 0, "y": 0, "w": 12, "h": 3}
        },
        {
            "id": "nearby_stations",
            "type": "map",
            "title": "Nearby Stations",
            "config": {"data_source": "/api/v1/stations/nearby"},
            "position": {"x": 0, "y": 3, "w": 12, "h": 6}
        }
    ],
    "default": [
         {
            "id": "welcome_widget",
            "type": "stat",
            "title": "Welcome",
            "config": {"message": "Welcome to Wezu"},
            "position": {"x": 0, "y": 0, "w": 12, "h": 4}
        }
    ]
}
