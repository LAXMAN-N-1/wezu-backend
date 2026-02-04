from sqlmodel import Session, select
from app.models.rbac import Role

def seed_roles(session: Session):
    """
    Seed valid roles if they don't exist.
    """
    roles = [
        {"name": "admin", "description": "Super Administrator with full access"},
        {"name": "customer", "description": "End user application user"},
        {"name": "dealer", "description": "Station owner/partner"},
        {"name": "station_manager", "description": "Manages specific station operations"},
        {"name": "technician", "description": "Maintenance and repair staff"},
        {"name": "logistics_manager", "description": "Oversees inventory movement"},
        {"name": "driver", "description": "Logistics driver for battery transport"},
        {"name": "warehouse_manager", "description": "Manages central inventory storage"},
        {"name": "support_agent", "description": "Customer support representative"},
        {"name": "finance_manager", "description": "Manages payments and settlements"},
        {"name": "inspector", "description": "Quality and safety inspector"},
        {"name": "franchise_owner", "description": "Regional franchise owner"},
        {"name": "marketing_manager", "description": "Promotions and campaigns"},
        {"name": "analyst", "description": "Data analytics and reporting"},
    ]
    
    for role_data in roles:
        existing_role = session.exec(select(Role).where(Role.name == role_data["name"])).first()
        if not existing_role:
            role = Role(
                name=role_data["name"],
                description=role_data["description"],
                permissions=[], # Permissions can be granularly added later
                is_system_role=True
            )
            session.add(role)
    
    session.commit()
