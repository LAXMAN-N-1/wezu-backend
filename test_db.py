from dotenv import load_dotenv
load_dotenv()
from app.db.session import engine
from sqlmodel import Session, select
from app.models.support import SupportTicket
from app.models.dealer import DealerProfile
from app.models.user import User

with Session(engine) as db:
    tickets = db.exec(select(SupportTicket)).all()
    print("Total tickets:", len(tickets))
    for t in tickets[:5]:
        print("Ticket ID:", t.id, " - owner user_id:", t.user_id)
        
    dealers = db.exec(select(DealerProfile)).all()
    for d in dealers:
        print("DealerProfile:", d.id, d.business_name, " - owner user_id:", d.user_id)

    users = db.exec(select(User).where(User.email.contains("dealer"))).all()
    for u in users:
        print("User:", u.id, u.email, u.full_name)
