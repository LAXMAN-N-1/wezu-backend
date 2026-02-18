from typing import List, Optional
from sqlmodel import Session, select
from app.models.rbac import Role, Permission, RolePermission
from app.models.role_right import RoleRight
from app.models.menu import Menu

class RBACService:
    @staticmethod
    def get_role_by_name(db: Session, name: str) -> Optional[Role]:
        return db.exec(select(Role).where(Role.name == name)).first()

    @staticmethod
    def get_user_permissions(db: Session, role_id: int) -> List[str]:
        """
        Get all permission slugs for a given role.
        """
        # This joins RolePermission and Permission to get the slugs
        # Assuming a link model RolePermission exists
        statement = (
            select(Permission.slug)
            .join(RolePermission)
            .where(RolePermission.role_id == role_id)
        )
        return list(db.exec(statement).all())

    @staticmethod
    def check_menu_access(db: Session, role_id: int, menu_name: str, permission_type: str = "view") -> bool:
        """
        Check if a role has a specific right on a menu.
        """
        statement = (
            select(RoleRight)
            .join(Menu)
            .where(RoleRight.role_id == role_id)
            .where(Menu.name == menu_name)
        )
        right = db.exec(statement).first()
        if not right:
            return False
        
        if permission_type == "view": return right.can_view
        if permission_type == "create": return right.can_create
        if permission_type == "edit": return right.can_edit
        if permission_type == "delete": return right.can_delete
        return False

    @staticmethod
    def assign_role_to_user(db: Session, user_id: int, role_id: int):
        from app.models.user import User
        user = db.get(User, user_id)
        if user:
            user.role_id = role_id
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    @staticmethod
    def get_menu_for_role(db: Session, role_id: int) -> List[dict]:
        """
        Get hierarchical menu structure for a role based on RoleRight.
        """
        # Fetch root menus where role has view permission
        statement = (
            select(Menu)
            .join(RoleRight)
            .where(RoleRight.role_id == role_id)
            .where(RoleRight.can_view == True)
            .where(Menu.parent_id == None)
            .where(Menu.is_active == True)
            .order_by(Menu.menu_order)
        )
        root_menus = db.exec(statement).all()
        
        menu_data = []
        for menu in root_menus:
            item = {
                "label": menu.display_name,
                "path": menu.route,
                "icon": menu.icon,
                "children": []
            }
            
            # Fetch children
            child_statement = (
                select(Menu)
                .join(RoleRight)
                .where(RoleRight.role_id == role_id)
                .where(RoleRight.can_view == True)
                .where(Menu.parent_id == menu.id)
                .where(Menu.is_active == True)
                .order_by(Menu.menu_order)
            )
            children = db.exec(child_statement).all()
            for child in children:
                item["children"].append({
                    "label": child.display_name,
                    "path": child.route,
                    "icon": child.icon
                })
            
            menu_data.append(item)
            
        return menu_data

rbac_service = RBACService()
