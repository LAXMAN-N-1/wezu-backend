from __future__ import annotations
from sqlmodel import Session, select
from app.models.rbac import Role

def seed_roles(session: Session):
    """
    Seed valid roles if they don't exist.
    """
    roles = [
        {"name": "super_admin", "description": "Full system authority", "category": "platform", "level": 100, "scope_owner": "global"},
        {"name": "operations_admin", "description": "Platform operations authority", "category": "platform", "level": 90, "scope_owner": "global"},
        {"name": "security_admin", "description": "Security policy and audit authority", "category": "platform", "level": 85, "scope_owner": "global"},
        {"name": "finance_admin", "description": "Finance and settlements authority", "category": "platform", "level": 85, "scope_owner": "global"},
        {"name": "support_manager", "description": "Support operations manager", "category": "support", "level": 70, "scope_owner": "global"},
        {"name": "support_agent", "description": "Support operations agent", "category": "support", "level": 60, "scope_owner": "global"},
        {"name": "logistics_manager", "description": "Logistics operations manager", "category": "logistics", "level": 70, "scope_owner": "global"},
        {"name": "dispatcher", "description": "Dispatch control role", "category": "logistics", "level": 60, "scope_owner": "global"},
        {"name": "fleet_manager", "description": "Fleet management role", "category": "logistics", "level": 60, "scope_owner": "global"},
        {"name": "warehouse_manager", "description": "Warehouse operations role", "category": "logistics", "level": 55, "scope_owner": "global"},
        {"name": "driver", "description": "Delivery and logistics field role", "category": "logistics", "level": 40, "scope_owner": "global"},
        {"name": "dealer_owner", "description": "Dealer principal owner role", "category": "dealer", "level": 60, "scope_owner": "global"},
        {"name": "dealer_manager", "description": "Dealer manager role template", "category": "dealer", "level": 55, "scope_owner": "global"},
        {"name": "dealer_inventory_staff", "description": "Dealer inventory role template", "category": "dealer", "level": 45, "scope_owner": "global"},
        {"name": "dealer_finance_staff", "description": "Dealer finance role template", "category": "dealer", "level": 45, "scope_owner": "global"},
        {"name": "dealer_support_staff", "description": "Dealer support role template", "category": "dealer", "level": 45, "scope_owner": "global"},
        {"name": "customer", "description": "Customer app role", "category": "customer", "level": 10, "scope_owner": "global"},
    ]
    
    for role_data in roles:
        existing_role = session.exec(select(Role).where(Role.name == role_data["name"])).first()
        if not existing_role:
            role = Role(
                name=role_data["name"],
                description=role_data["description"],
                category=role_data.get("category", "system"),
                level=role_data.get("level", 0),
                scope_owner=role_data.get("scope_owner", "global"),
                permissions=[], # Permissions can be granularly added later
                is_system_role=True
            )
            session.add(role)
    
    session.commit()
