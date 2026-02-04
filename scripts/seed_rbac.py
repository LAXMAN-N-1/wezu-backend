from sqlmodel import Session, select
from app.db.session import engine
from app.models.rbac import Role, Permission, RolePermission
from app.models.admin_user import AdminUser

def seed_rbac():
    """
    Seeds the database with default Roles and Permissions.
    """
    db = Session(engine)
    
    # Ensure tables exist (temporary dev convenience)
    from sqlmodel import SQLModel
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
    
    print("Seeding Permissions...")
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
        "Super Admin": {
            "desc": "Full access to everything",
            "is_system": True,
            "perms": "ALL" 
        },
        "Platform Admin": {
            "desc": "Senior leadership with broad access",
            "is_system": False,
            "perms": ["vendor:read", "vendor:approve", "vendor:suspend", "station:create", "station:read", "station:update", "battery:read", "customer:read", "finance:read_dashboard", "analytics:read"]
        },
        "Finance Manager": {
            "desc": "Manages financial operations",
            "is_system": False,
            "perms": ["finance:read_dashboard", "finance:read_transactions", "finance:process_refund", "finance:approve_settlement", "finance:export_reports", "vendor:read"]
        },
        "Operations Manager": {
            "desc": "Manages vendors, stations, batteries",
            "is_system": False,
            "perms": ["vendor:create", "vendor:read", "vendor:update", "station:create", "station:read", "station:update", "station:delete", "station:manage_slots", "battery:create", "battery:read", "battery:update"]
        },
        "Support Agent": {
            "desc": "Basic customer support",
            "is_system": False,
            "perms": ["customer:read", "support:read_tickets", "support:update_tickets"]
        }
    }
    
    print("\nSeeding Roles...")
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
            
    print("\nRBAC Seeding Complete!")

if __name__ == "__main__":
    seed_rbac()
