from enum import Enum

class RoleEnum(str, Enum):
    ADMIN = "admin"
    DEALER = "dealer"
    DRIVER = "driver"
    CUSTOMER = "customer"
    SUPER_ADMIN = "super_admin"
    SUPPORT_AGENT = "support_agent"
    LOGISTICS = "logistics"
