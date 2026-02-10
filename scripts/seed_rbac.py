import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.role import Role
from app.models.menu import Menu
from app.models.role_right import RoleRight

def seed_rbac():
    with Session(engine) as session:
        print("Seeding RBAC data...")

        # 1. Seed Roles
        roles_data = ["super_admin", "admin", "manager", "dealer", "user"]
        roles = {}
        for role_name in roles_data:
            role = session.exec(select(Role).where(Role.name == role_name)).first()
            if not role:
                role = Role(name=role_name)
                session.add(role)
                session.flush()
                print(f"Created role: {role_name}")
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
        manager_menus = ["dashboard", "stations", "batteries", "rentals", "maintenance"]
        for m_name in manager_menus:
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
        dealer_rights = {
            "dashboard": (True, False, False, False),
            "stations": (True, False, False, False),
            "batteries": (True, False, False, False),
            "rentals": (True, True, True, False),
        }
        for m_name, (v, c, e, d) in dealer_rights.items():
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
        print("RBAC Seeding complete.")

if __name__ == "__main__":
    seed_rbac()
