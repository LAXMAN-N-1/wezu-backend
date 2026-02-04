from typing import List, Set, Dict, Any
from sqlmodel import Session, select
from app.models.rbac import Role, Permission, UserRole, AdminUserRole
from app.models.user import User
from app.models.admin_user import AdminUser

class RBACService:
    @staticmethod
    def get_role_permissions(db: Session, role_id: int, visited_roles: Set[int] = None) -> Set[str]:
        """
        Recursively fetch all permission slugs for a role including inherited ones.
        """
        if visited_roles is None:
            visited_roles = set()
        
        if role_id in visited_roles:
            return set()
        
        visited_roles.add(role_id)
        role = db.get(Role, role_id)
        if not role:
            return set()
        
        permissions = {p.slug for p in role.permissions}
        
        # Inherit from parent
        if role.parent_id:
            permissions.update(RBACService.get_role_permissions(db, role.parent_id, visited_roles))
            
        return permissions

    @staticmethod
    def get_user_permissions(db: Session, user_id: int, is_admin: bool = False) -> Set[str]:
        """
        Get all permissions for a specific user or admin.
        """
        if is_admin:
            roles = db.exec(select(Role).join(AdminUserRole).where(AdminUserRole.admin_id == user_id)).all()
        else:
            roles = db.exec(select(Role).join(UserRole).where(UserRole.user_id == user_id)).all()
            
        all_permissions = set()
        for role in roles:
            all_permissions.update(RBACService.get_role_permissions(db, role.id))
            
        return all_permissions

    @staticmethod
    def generate_menu_config(permissions: Set[str]) -> Dict[str, Any]:
        """
        Generate dynamic menu structure based on user permissions.
        This follows the schema requested in the user prompt.
        """
        # Define baseline menu template
        menu = {
            "dashboard": {
                "enabled": True,
                "icon": "dashboard",
                "route": "/dashboard",
                "label": "Dashboard",
                "order": 1
            }
        }
        
        # Mapping permissions to menu items
        if "battery:view" in permissions or "battery:view:all" in permissions:
            menu["batteries"] = {
                "enabled": True,
                "icon": "battery_charging",
                "route": "/batteries",
                "label": "Battery Management",
                "order": 2,
                "submenu": [
                    {
                        "label": "All Batteries",
                        "route": "/batteries/list",
                        "permission": "battery:view:all",
                        "enabled": "battery:view:all" in permissions
                    },
                    {
                        "label": "Add Battery",
                        "route": "/batteries/add",
                        "permission": "battery:create",
                        "enabled": "battery:create" in permissions
                    },
                    {
                        "label": "Battery Health",
                        "route": "/batteries/health",
                        "permission": "battery:view:health",
                        "enabled": "battery:view:health" in permissions or "battery:view:all" in permissions
                    }
                ]
            }

        if "station:view" in permissions or "station:view:all" in permissions:
            menu["stations"] = {
                "enabled": True,
                "icon": "store",
                "route": "/stations",
                "label": "Stations",
                "order": 3
            }
            
        if "analytics:view" in permissions:
            menu["analytics"] = {
                "enabled": True,
                "icon": "analytics",
                "route": "/analytics",
                "label": "Analytics",
                "order": 4
            }
            
        return menu
