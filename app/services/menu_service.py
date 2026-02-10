from typing import List, Optional
from sqlmodel import Session, select
from app.models.menu import Menu
from app.schemas.menu import MenuCreate, MenuUpdate

class MenuService:
    @staticmethod
    def create_menu(db: Session, menu_in: MenuCreate) -> Menu:
        if menu_in.parent_id == 0:
            menu_in.parent_id = None
        db_menu = Menu.from_orm(menu_in)
        db.add(db_menu)
        db.commit()
        db.refresh(db_menu)
        return db_menu

    @staticmethod
    def get_menu(db: Session, menu_id: int) -> Optional[Menu]:
        return db.get(Menu, menu_id)

    @staticmethod
    def get_menus(db: Session, skip: int = 0, limit: int = 100) -> List[Menu]:
        return db.exec(select(Menu).where(Menu.parent_id == None).offset(skip).limit(limit)).all()

    @staticmethod
    def update_menu(db: Session, menu_id: int, menu_in: MenuUpdate) -> Optional[Menu]:
        db_menu = db.get(Menu, menu_id)
        if not db_menu:
            return None
        
        if menu_in.parent_id == 0:
            menu_in.parent_id = None
            
        menu_data = menu_in.dict(exclude_unset=True)
        for key, value in menu_data.items():
            setattr(db_menu, key, value)
        db.add(db_menu)
        db.commit()
        db.refresh(db_menu)
        return db_menu

    @staticmethod
    def delete_menu(db: Session, menu_id: int) -> bool:
        db_menu = db.get(Menu, menu_id)
        if not db_menu:
            return False
        db.delete(db_menu)
        db.commit()
        return True

menu_service = MenuService()
