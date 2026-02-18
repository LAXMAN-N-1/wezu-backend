import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlmodel import Session, select, SQLModel
from app.core.database import engine

# Import all models to ensure SQLModel registry is complete
from app import models 

# Imports for Menu-Based RBAC (HEAD)
from app.models.menu import Menu
from app.models.role_right import RoleRight

# Imports for Permission-Based RBAC (Main)
from app.models.rbac import Role, Permission, RolePermission
from app.models.admin_user import AdminUser

def seed_menu_rbac():
    """
    Seeds Menu-based RBAC (from Chandu branch)
    """
    with Session(engine) as session:
        print("Seeding Menu-based RBAC data...")

        # 1. Seed Roles (Legacy/Simple)
        roles_data = ["super_admin", "admin", "manager", "dealer", "user"]
        roles = {}
        for role_name in roles_data:
            # Note: Role model might overlap with RBAC Role model if table names same
            # Assuming they map to same table or allow co-existence
            # Note: Role model might overlap with RBAC Role model if table names same
            # Assuming they map to same table or allow co-existence
            role = session.exec(select(Role).where(Role.name == role_name)).first()
            if not role:
                role = Role(name=role_name)
                session.add(role)
                session.flush()
                print(f"Created role (legacy): {role_name}")
            roles[role_name] = role

        # 2. Seed Menus
        menus_data = [
            {"name": "dashboard", "display_name": "Dashboard", "route": "/dashboard", "icon": "dashboard"},
            {"name": "stations", "display_name": "Stations", "route": "/stations", "icon": "ev_station"},
            {"name": "batteries", "display_name": "Batteries", "route": "/batteries", "icon": "battery_charging_full"},
            {"name": "rentals", "display_name": "Rentals", "route": "/rentals", "icon": "shopping_cart"},
            {"name": "users", "display_name": "User Management", "route": "/users", "icon": "people"},
            {"name": "payments", "display_name": "Payments", "route": "/payments", "icon": "payments"},
            {"name": "maintenance", "display_name": "Maintenance", "route": "/maintenance", "icon": "build"},
            {"name": "branches", "display_name": "Branches", "route": "/branches", "icon": "branch"},
            {"name": "organizations", "display_name": "Organizations", "route": "/organizations", "icon": "business"},
            {"name": "roles", "display_name": "Role Management", "route": "/roles", "icon": "admin_panel_settings"},
            {"name": "menus", "display_name": "Menu Management", "route": "/menus", "icon": "menu"},
            {"name": "role_rights", "display_name": "Permission Management", "route": "/role-rights", "icon": "security"},
            {"name": "i18n", "display_name": "Translations", "route": "/i18n", "icon": "language"},
        ]
        
        menus = {}
        for m_data in menus_data:
            menu = session.exec(select(Menu).where(Menu.name == m_data["name"])).first()
            if not menu:
                menu = Menu(**m_data)
                session.add(menu)
                session.flush()
                print(f"Created menu: {m_data['name']}")
            menus[m_data["name"]] = menu

        # 3. Seed Role Rights
        
        # Super Admin -> Full Access to Everything
        if "super_admin" in roles:
            for menu in menus.values():
                right = session.exec(select(RoleRight).where(
                    RoleRight.role_id == roles["super_admin"].id,
                    RoleRight.menu_id == menu.id
                )).first()
                if not right:
                    session.add(RoleRight(
                        role_id=roles["super_admin"].id,
                        menu_id=menu.id,
                        can_view=True, can_create=True, can_edit=True, can_delete=True
                    ))

        # Manager -> Full Access to Stations, Batteries, Rentals, Maintenance
        if "manager" in roles:
            manager_menus = ["dashboard", "stations", "batteries", "rentals", "maintenance"]
            for m_name in manager_menus:
                if m_name in menus:
                    menu = menus[m_name]
                    right = session.exec(select(RoleRight).where(
                        RoleRight.role_id == roles["manager"].id,
                        RoleRight.menu_id == menu.id
                    )).first()
                    if not right:
                        session.add(RoleRight(
                            role_id=roles["manager"].id,
                            menu_id=menu.id,
                            can_view=True, can_create=True, can_edit=True, can_delete=False
                        ))

        # Dealer -> View/Create Rentals, View Stations/Batteries
        if "dealer" in roles:
            dealer_rights = {
                "dashboard": (True, False, False, False),
                "stations": (True, False, False, False),
                "batteries": (True, False, False, False),
                "rentals": (True, True, True, False),
            }
            for m_name, (v, c, e, d) in dealer_rights.items():
                if m_name in menus:
                    menu = menus[m_name]
                    right = session.exec(select(RoleRight).where(
                        RoleRight.role_id == roles["dealer"].id,
                        RoleRight.menu_id == menu.id
                    )).first()
                    if not right:
                        session.add(RoleRight(
                            role_id=roles["dealer"].id,
                            menu_id=menu.id,
                            can_view=v, can_create=c, can_edit=e, can_delete=d
                        ))

        session.commit()
        print("Menu-based RBAC Seeding complete.")

def seed_permissions_rbac():
    """
    Seeds Permission-based RBAC (from Main branch)
    """
    with Session(engine) as db:
        print("Seeding Permission-based RBAC...")
        
        # Ensure tables exist (temporary dev convenience)
        SQLModel.metadata.create_all(engine)
        
        # 1. Define Permissions
        # Schema: (module, action, description)
        permissions_list = [
            # Vendor Management
            ("vendor", "create", "Create new vendor"),
            ("vendor", "read", "View vendor details"),
            ("vendor", "update", "Edit vendor details"),
            ("vendor", "delete", "Delete vendor"),
            ("vendor", "approve", "Approve vendor onboarding"),
            ("vendor", "suspend", "Suspend vendor account"),
            
            # Station Management
            ("station", "create", "Create new station"),
            ("station", "read", "View station details"),
            ("station", "update", "Edit station details"),
            ("station", "delete", "Delete station"),
            ("station", "manage_slots", "Manage battery slots"),
            
            # Battery Management
            ("battery", "create", "Register new battery"),
            ("battery", "read", "View battery details"),
            ("battery", "update", "Update battery status"),
            ("battery", "retire", "Mark battery as retired"),
            
            # Customer Management
            ("customer", "read", "View customer profiles"),
            ("customer", "update", "Edit customer details"),
            ("customer", "suspend", "Suspend customer account"),
            ("customer", "wallet_read", "View customer wallet balance"),
            ("customer", "wallet_adjust", "Adjust customer wallet balance"),
            
            # Financial Operations
            ("finance", "read_dashboard", "View financial dashboard"),
            ("finance", "read_transactions", "View transaction history"),
            ("finance", "process_refund", "Process refunds"),
            ("finance", "approve_settlement", "Approve vendor settlements"),
            ("finance", "export_reports", "Export financial reports"),
            
            # Analytics
            ("analytics", "read", "View analytics dashboard"),
            ("analytics", "export", "Export analytics data"),
            
            # Support
            ("support", "read_tickets", "View support tickets"),
            ("support", "update_tickets", "Respond to/close tickets"),
            
            # System / RBAC (Super Admin only usually)
            ("system", "manage_users", "Create and manage admin users"),
            ("system", "manage_roles", "Create and manage roles"),
            ("system", "view_audit_logs", "View system audit logs"),
        ]
        
        created_perms = []
        for module, action, desc in permissions_list:
            slug = f"{module}:{action}"
            perm = db.exec(select(Permission).where(Permission.slug == slug)).first()
            if not perm:
                perm = Permission(slug=slug, module=module, action=action, description=desc)
                db.add(perm)
                db.commit()
                db.refresh(perm)
                print(f"  + Created permission: {slug}")
            created_perms.append(perm)
            
        # 2. Define Roles
        roles_def = {
            "super_admin": {
                "desc": "Full access to everything",
                "is_system": True,
                "perms": "ALL" 
            },
            "platform_admin": {
                "desc": "Senior leadership with broad access",
                "is_system": False,
                "perms": ["vendor:read", "vendor:approve", "vendor:suspend", "station:create", "station:read", "station:update", "battery:read", "customer:read", "finance:read_dashboard", "analytics:read"]
            },
            # "finance_manager": { ... } - Keeping keys lowercase to match potential existing roles
            "finance_manager": {
                "desc": "Manages financial operations",
                "is_system": False,
                "perms": ["finance:read_dashboard", "finance:read_transactions", "finance:process_refund", "finance:approve_settlement", "finance:export_reports", "vendor:read"]
            },
            "operations_manager": {
                "desc": "Manages vendors, stations, batteries",
                "is_system": False,
                "perms": ["vendor:create", "vendor:read", "vendor:update", "station:create", "station:read", "station:update", "station:delete", "station:manage_slots", "battery:create", "battery:read", "battery:update"]
            },
            "support_agent": {
                "desc": "Basic customer support",
                "is_system": False,
                "perms": ["customer:read", "support:read_tickets", "support:update_tickets"]
            },
            "driver": {
                "desc": "Delivery driver with limited access",
                "is_system": False,
                "perms": ["battery:read", "station:read", "station:read"] 
            },
            "dealer": {
                "desc": "Station dealer with access to own resources",
                "is_system": False,
                "perms": ["station:read", "station:create", "station:update", "battery:read", "battery:create", "battery:update", "customer:read"]
            }
        }
        
        for role_name, config in roles_def.items():
            role = db.exec(select(Role).where(Role.name == role_name)).first()
            if not role:
                role = Role(name=role_name, description=config["desc"], is_system_role=config["is_system"])
                db.add(role)
                db.commit()
                db.refresh(role)
                print(f"  + Created role: {role_name}")
                
                # Assign Permissions
                perms_to_assign = []
                if config["perms"] == "ALL":
                    perms_to_assign = created_perms
                else:
                    for slug in config["perms"]:
                        p = next((x for x in created_perms if x.slug == slug), None)
                        if p:
                            perms_to_assign.append(p)
                
                for p in perms_to_assign:
                    link = RolePermission(role_id=role.id, permission_id=p.id)
                    db.add(link)
                db.commit()
                print(f"    - Assigned {len(perms_to_assign)} permissions")
                
        print("Permission-based RBAC Seeding Complete!")

if __name__ == "__main__":
    # Execute both seeding logic
    try:
        seed_permissions_rbac()
    except Exception as e:
        print(f"Error seeding permissions RBAC: {e}")
        
    try:
        seed_menu_rbac()
    except Exception as e:
        print(f"Error seeding menu RBAC: {e}")
