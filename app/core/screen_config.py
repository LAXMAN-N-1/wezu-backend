from __future__ import annotations
from typing import Dict, Any

# Master Screen Configuration
# Define all available columns, actions, and filters for each screen here.
# The API will dynamically filter these based on user permissions.

MASTER_SCREEN_CONFIG: Dict[str, Any] = {
    "battery_list": {
        "screen_id": "battery_list",
        "columns": [
            {
                "field": "battery_id",
                "label": "ID",
                "visible": True,
                "sortable": True
            },
            {
                "field": "status",
                "label": "Status",
                "visible": True,
                "sortable": True
            },
            {
                "field": "soc",
                "label": "SoC",
                "visible": True,
                "sortable": True
            },
            {
                "field": "financial_data",
                "label": "Cost",
                "visible": True, 
                "permission_required": "finance:view"
            }
        ],
        "actions": [
            {
                "id": "view_details",
                "label": "View Details",
                "enabled": True
            },
            {
                "id": "edit",
                "label": "Edit",
                "enabled": True,
                "permission": "battery:update"
            },
            {
                "id": "delete",
                "label": "Delete",
                "enabled": True,
                "permission": "battery:delete"
            }
        ],
        "filters": [
            {"id": "status", "type": "select", "options": ["active", "maintenance", "retired"]},
            {"id": "soc_min", "type": "number", "label": "Min SoC"}
        ],
        "bulk_actions": [
            {"id": "export_csv", "label": "Export CSV"}
        ]
    }
}
