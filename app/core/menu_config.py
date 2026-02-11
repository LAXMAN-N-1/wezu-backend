from typing import List, Dict, Any, Optional

# Define the Master Menu Structure
# This serves as the single source of truth for all possible menu items.
# The endpoint will filter this list based on user permissions.

MASTER_MENU: List[Dict[str, Any]] = [
    {
        "id": "dashboard",
        "label": "Dashboard",
        "icon": "dashboard",
        "route": "/dashboard",
        "order": 1,
        "enabled": True,
        # No specific permission required means available to all authenticated users
    },
    {
        "id": "batteries",
        "label": "Batteries",
        "icon": "battery",
        "route": "/batteries",
        "order": 2,
        "enabled": True,
        "permission": "battery:view", # Parent permission
        "submenu": [
            {
                "id": "batteries_list",
                "label": "All Batteries",
                "route": "/batteries/list",
                "permission": "battery:view:all",
                "enabled": True,
                "order": 1
            },
            {
                "id": "batteries_map",
                "label": "Battery Map",
                "route": "/batteries/map",
                "permission": "battery:view:map", 
                "enabled": True,
                "order": 2
            }
        ]
    },
     {
        "id": "stations",
        "label": "Stations",
        "icon": "ev_station",
        "route": "/stations",
        "order": 3,
        "enabled": True,
        "permission": "station:view",
        "submenu": [
            {
                "id": "stations_list",
                "label": "All Stations",
                "route": "/stations/list",
                "permission": "station:view:all",
                "enabled": True,
                "order": 1
            },
            {
                "id": "stations_map",
                "label": "Station Map",
                "route": "/stations/map",
                "permission": "station:view:map",
                "enabled": True,
                "order": 2
            }
        ]
    },
    {
        "id": "finance",
        "label": "Finance",
        "icon": "payments",
        "route": "/finance",
        "order": 4,
        "enabled": True,
        "permission": "finance:view",
        "submenu": [
             {
                "id": "transactions",
                "label": "Transactions",
                "route": "/finance/transactions",
                "permission": "finance:view:transactions",
                "enabled": True,
                 "order": 1
            },
            {
                "id": "invoices",
                "label": "Invoices",
                "route": "/finance/invoices",
                "permission": "finance:view:invoices",
                "enabled": True,
                 "order": 2
            }
        ]
    },
    {
        "id": "users",
        "label": "Users & Roles",
        "icon": "group",
        "route": "/admin/users",
        "order": 5,
        "enabled": True,
        "permission": "user:view", # Typically admin only
         "submenu": [
             {
                "id": "users_list",
                "label": "All Users",
                "route": "/admin/users/list",
                "permission": "user:view:all",
                "enabled": True,
                 "order": 1
            },
            {
                "id": "roles_list",
                "label": "Roles",
                "route": "/admin/roles",
                "permission": "role:view",
                "enabled": True,
                 "order": 2
            }
        ]
    },
    {
        "id": "settings",
        "label": "Settings",
        "icon": "settings",
        "route": "/settings",
        "order": 99,
        "enabled": True,
        "permission": "settings:view"
    }
]
