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
        "permission": "battery:view:global", # Parent permission
        "submenu": [
            {
                "id": "batteries_list",
                "label": "All Batteries",
                "route": "/batteries/list",
                "permission": "battery:view:global",
                "enabled": True,
                "order": 1
            },
            {
                "id": "batteries_map",
                "label": "Battery Map",
                "route": "/batteries/map",
                "permission": "battery:view:global",
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
        "permission": "station:view:global",
        "submenu": [
            {
                "id": "stations_list",
                "label": "All Stations",
                "route": "/stations/list",
                "permission": "station:view:global",
                "enabled": True,
                "order": 1
            },
            {
                "id": "stations_map",
                "label": "Station Map",
                "route": "/stations/map",
                "permission": "station:view:global",
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
        "permission": "finance:view:global",
        "submenu": [
             {
                "id": "transactions",
                "label": "Transactions",
                "route": "/finance/transactions",
                "permission": "finance:view:global",
                "enabled": True,
                 "order": 1
            },
            {
                "id": "invoices",
                "label": "Invoices",
                "route": "/finance/invoices",
                "permission": "finance:view:global",
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
        "permission": "users:view:global", # Typically admin only
         "submenu": [
             {
                "id": "users_list",
                "label": "All Users",
                "route": "/admin/users/list",
                "permission": "users:view:global",
                "enabled": True,
                 "order": 1
            },
            {
                "id": "roles_list",
                "label": "Roles",
                "route": "/admin/roles",
                "permission": "roles:view:global",
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
        "permission": "settings:view:global"
    }
]
