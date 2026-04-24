from __future__ import annotations
from enum import Enum

class RoleEnum(str, Enum):
    SUPER_ADMIN = "super_admin"
    OPERATIONS_ADMIN = "operations_admin"
    SECURITY_ADMIN = "security_admin"
    FINANCE_ADMIN = "finance_admin"
    SUPPORT_MANAGER = "support_manager"
    SUPPORT_AGENT = "support_agent"
    LOGISTICS_MANAGER = "logistics_manager"
    DISPATCHER = "dispatcher"
    FLEET_MANAGER = "fleet_manager"
    WAREHOUSE_MANAGER = "warehouse_manager"
    DEALER_OWNER = "dealer_owner"
    DEALER_MANAGER = "dealer_manager"
    DEALER_INVENTORY_STAFF = "dealer_inventory_staff"
    DEALER_FINANCE_STAFF = "dealer_finance_staff"
    DEALER_SUPPORT_STAFF = "dealer_support_staff"
    DRIVER = "driver"
    CUSTOMER = "customer"

    # Legacy aliases retained for compatibility paths.
    ADMIN = "operations_admin"
    DEALER = "dealer_owner"
    LOGISTICS = "logistics_manager"
