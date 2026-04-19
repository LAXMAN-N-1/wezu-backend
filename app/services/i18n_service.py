from __future__ import annotations
from sqlmodel import Session, select
from app.core.database import engine
from app.models.i18n import Translation

class I18nService:
    @staticmethod
    def get_translation(key: str, lang: str = "en") -> str:
        with Session(engine) as session:
            t = session.exec(select(Translation).where(
                Translation.key == key,
                Translation.language_code == lang
            )).first()
            if t:
                return t.value
            
            # Fallback to English if not requested
            if lang != "en":
                t_en = session.exec(select(Translation).where(
                    Translation.key == key,
                    Translation.language_code == "en"
                )).first()
                if t_en:
                    return t_en.value
            
            return key # Return key if missing

    @staticmethod
    def set_translation(key: str, lang: str, value: str):
        with Session(engine) as session:
            existing = session.exec(select(Translation).where(
                Translation.key == key,
                Translation.language_code == lang
            )).first()
            
            if existing:
                existing.value = value
                session.add(existing)
            else:
                new_t = Translation(key=key, language_code=lang, value=value)
                session.add(new_t)
            session.commit()
