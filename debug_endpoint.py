from sqlmodel import Session, select
from app.core.database import engine
from app.api.admin.users import list_users, get_user_summary
from app.models.user import User

with Session(engine) as db:
    user = db.exec(select(User).limit(1)).first()
    if not user:
        print("No users found.")
    else:
        try:
            print("Testing get_user_summary...")
            summary = get_user_summary(current_user=user, db=db)
            print("Summary OK:", summary)
        except Exception as e:
            print("Summary ERROR:", repr(e))

        try:
            print("Testing list_users...")
            users_list = list_users(current_user=user, db=db)
            print("List users OK, count:", users_list["total_count"])
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("List ERROR:", repr(e))
