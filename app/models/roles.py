from enum import Enum

class RoleEnum(str, Enum):
    ADMIN = "admin"
    DEALER = "dealer"
    DRIVER = "driver"
    CUSTOMER = "customer"
