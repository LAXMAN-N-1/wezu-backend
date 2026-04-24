from __future__ import annotations
"""
Seed script for Support Module.
Seeds: Tickets (from customers, dealers, drivers), Knowledge Base articles, Ticket Messages
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone; UTC = timezone.utc
from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User
from app.models.support import SupportTicket, TicketMessage, TicketStatus, TicketPriority
from app.models.faq import FAQ

def random_date(days_back=60):
    return datetime.now(UTC) - timedelta(days=random.randint(0, days_back), hours=random.randint(0, 23), minutes=random.randint(0, 59))


def seed_support():
    with Session(engine) as db:
        users = db.exec(select(User)).all()
        if not users:
            print("ERROR: No users. Run base seed first.")
            return
        user_ids = [u.id for u in users]
        admin_ids = [u.id for u in users if hasattr(u, "user_type") and getattr(u.user_type, "value", "") in ("admin", "superadmin")]
        if not admin_ids:
            admin_ids = user_ids[:2]

        # ─── TICKETS ──────────────────────────────────────────────────────
        existing = db.exec(select(SupportTicket)).all()
        if len(existing) < 10:
            print("Seeding support tickets...")

            tickets_data = [
                # Customer tickets
                ("Battery not charging properly", "My battery ID #2045 stops charging at 80%. It's been happening for 3 days now.", "technical", "high", "customer"),
                ("Refund not received for cancelled rental", "I cancelled my rental 5 days ago but haven't received my deposit refund yet. Order #1234.", "billing", "high", "customer"),
                ("App crashing on payment page", "The app crashes every time I try to make a payment on Samsung Galaxy S23. Android 14.", "technical", "critical", "customer"),
                ("Wrong battery delivered", "I ordered a 60V battery but received a 48V one. Order #5678.", "hardware", "high", "customer"),
                ("How to extend rental period?", "I want to extend my current rental for another month. How do I do this?", "general", "low", "customer"),
                ("Station QR code not scanning", "The QR code at Madhapur station (Slot 3) is damaged and won't scan.", "hardware", "medium", "customer"),
                ("Account locked after wrong password", "Entered wrong password 3 times and now my account is locked. Please help.", "account", "medium", "customer"),
                ("Request for invoice copy", "Please provide me a copy of my invoice for Feb 2026. GSTIN: 29AABCU9462F1Z1.", "billing", "low", "customer"),
                ("Battery range less than expected", "The battery only gives 35km range instead of advertised 50km.", "technical", "medium", "customer"),
                ("Subscription plan upgrade query", "Want to upgrade from Basic to Premium plan. What are the benefits?", "general", "low", "customer"),
                # Dealer tickets
                ("Stock replenishment delay", "Our station at Kondapur hasn't been restocked in 4 days. Customers are complaining. DealerID: D-104.", "logistics", "critical", "dealer"),
                ("Commission calculation discrepancy", "March settlement shows ₹15,200 commission but my calculation shows ₹18,400. Please check.", "billing", "high", "dealer"),
                ("Station slot malfunction", "Slots 2 and 5 at our Gachibowli station are showing errors. Need maintenance.", "hardware", "high", "dealer"),
                ("Dashboard data not updating", "Revenue dashboard hasn't updated since yesterday. Shows old figures.", "technical", "medium", "dealer"),
                ("Request for promotional materials", "Need updated banners and flyers for our new Jubilee Hills station opening.", "general", "low", "dealer"),
                ("KYC document rejection reason unclear", "My KYC application was rejected but the reason given is vague. Application #KYC-789.", "account", "medium", "dealer"),
                # Driver tickets
                ("Delivery app GPS not working", "GPS tracking is not updating in real-time. Using iPhone 15. Happens intermittently.", "technical", "high", "driver"),
                ("Unable to mark delivery as completed", "Order #DEL-456 stuck at 'in_transit'. Can't mark as delivered even after customer confirmation.", "technical", "critical", "driver"),
                ("Route optimization suggestion", "The Miyapur-Kukatpally route has a blocked road at Miyapur Circle. Suggest alternate.", "logistics", "medium", "driver"),
                ("Payment for extra deliveries pending", "Completed 15 extra deliveries last week but payment not reflected in my wallet.", "billing", "high", "driver"),
                # Internal tickets
                ("Database backup verification", "Monthly DB backup verification for March needed. Check integrity of all tables.", "technical", "medium", "internal"),
                ("API rate limiting implementation", "Need to implement rate limiting on public APIs. Currently no throttling.", "technical", "high", "internal"),
                ("Customer data export request", "Legal team needs anonymized customer data export for compliance audit.", "general", "medium", "internal"),
                ("SSL certificate renewal", "SSL cert for api.wezu.com expires in 30 days. Schedule renewal.", "technical", "high", "internal"),
                ("Monthly MIS report generation", "Generate P&L, user growth, and station utilization reports for board meeting.", "general", "medium", "internal"),
                # More customer tickets with various statuses
                ("Swap station location suggestion", "Please add a swap station near Secunderabad Railway station. High demand area.", "general", "low", "customer"),
                ("Battery making unusual noise", "Battery is making a buzzing sound during discharge. Serial #BAT-1089.", "hardware", "critical", "customer"),
                ("Multiple charges for single rental", "I was charged 3 times for a single rental. Transaction IDs: T-123, T-124, T-125.", "billing", "critical", "customer"),
                ("App showing wrong station availability", "Hitech City station shows 5 batteries available but actually all slots are empty.", "technical", "high", "customer"),
                ("Referral code not working", "Applied referral code WEZU2026 but didn't get the ₹200 credit.", "billing", "low", "customer"),
                ("Request for bulk rental pricing", "Our company (50 employees) wants to rent batteries in bulk. Need corporate pricing.", "general", "medium", "customer"),
                ("Late fee waiver request", "Returned battery 2 hours late due to traffic. Requesting late fee waiver of ₹150.", "billing", "medium", "customer"),
                ("Station cleanliness complaint", "Kukatpally station is very dirty and has broken glass near the charging slots.", "general", "medium", "customer"),
                ("Two-wheeler compatibility query", "Is the 48V battery compatible with Ather 450X scooter?", "general", "low", "customer"),
                ("Emergency roadside assistance need", "Battery died mid-trip at LB Nagar. Need emergency swap or pickup.", "emergency", "critical", "customer"),
            ]

            statuses = [TicketStatus.OPEN, TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED]
            
            for subject, desc, category, priority_str, source in tickets_data:
                priority_val = {"low": TicketPriority.LOW, "medium": TicketPriority.MEDIUM, "high": TicketPriority.HIGH, "critical": TicketPriority.CRITICAL}[priority_str]
                status = random.choice(statuses)
                
                # Pick user based on source
                source_users = [u for u in users if (getattr(u.user_type, "value", "customer") if hasattr(u, "user_type") else "customer").lower() == source] or [random.choice(users)]
                ticket_user = random.choice(source_users)
                
                assigned = random.choice(admin_ids) if status != TicketStatus.OPEN else None
                created = random_date(45)
                resolved = None
                if status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
                    resolved = created + timedelta(hours=random.randint(1, 72))
                
                ticket = SupportTicket(
                    user_id=ticket_user.id,
                    assigned_to=assigned,
                    subject=subject,
                    description=desc,
                    status=status,
                    priority=priority_val,
                    category=category,
                    created_at=created,
                    updated_at=created + timedelta(hours=random.randint(0, 24)),
                    resolved_at=resolved,
                )
                db.add(ticket)
            db.commit()
            print(f"  ✓ Created {len(tickets_data)} tickets")

            # ─── TICKET MESSAGES ──────────────────────────────────────────
            print("Seeding ticket messages...")
            tickets = db.exec(select(SupportTicket)).all()
            
            agent_responses = [
                "Thank you for reaching out. We're looking into this issue right now.",
                "I've escalated this to our technical team. You should hear back within 2 hours.",
                "We've identified the issue and a fix is being deployed.",
                "Your refund has been processed. It will reflect in 3-5 business days.",
                "I've scheduled a maintenance visit for the station. Should be fixed by tomorrow.",
                "Could you please provide your order ID so we can investigate further?",
                "We apologize for the inconvenience. Here's a ₹100 credit for the trouble.",
                "This has been resolved. Please check and confirm if it's working now.",
                "I'm assigning this to our specialized team for faster resolution.",
                "We've updated the system. Please try again and let us know if the issue persists.",
            ]
            
            customer_followups = [
                "Thanks for the quick response!",
                "It's still not working. Can you check again?",
                "Yes, that fixed it. Thank you!",
                "How long will this take? It's been a while.",
                "I've attached a screenshot of the error.",
                "The issue is resolved now. Appreciate the help.",
            ]
            
            for ticket in tickets:
                # 2-5 messages per ticket
                num_msgs = random.randint(2, 5)
                base_time = ticket.created_at
                
                for m in range(num_msgs):
                    is_agent = m % 2 == 1
                    is_first_customer_msg = m == 0
                    
                    msg = TicketMessage(
                        ticket_id=ticket.id,
                        sender_id=random.choice(admin_ids) if is_agent else ticket.user_id,
                        message=ticket.description if is_first_customer_msg else (random.choice(agent_responses) if is_agent else random.choice(customer_followups)),
                        is_internal_note=(is_agent and random.random() < 0.15),
                        created_at=base_time + timedelta(minutes=random.randint(5, 180) * (m + 1)),
                    )
                    db.add(msg)
            db.commit()
            print(f"  ✓ Created messages for {len(tickets)} tickets")

        # ─── KNOWLEDGE BASE ───────────────────────────────────────────────
        existing_kb = db.exec(select(FAQ)).all()
        if len(existing_kb) < 10:
            print("Seeding knowledge base articles...")
            
            kb_articles = [
                # Getting Started
                ("How do I rent a battery?", "1. Open the WEZU app\n2. Find your nearest station using the map\n3. Scan the QR code on the station\n4. Select a battery from available slots\n5. Confirm the rental and make payment\n6. The slot will unlock automatically\n7. Take your battery and go!", "getting_started", True, 156, 8),
                ("What payment methods are accepted?", "WEZU accepts:\n• UPI (Google Pay, PhonePe, Paytm)\n• Credit/Debit Cards (Visa, Mastercard, RuPay)\n• Net Banking\n• WEZU Wallet\n\nAll transactions are secured with 256-bit encryption.", "payment", True, 89, 3),
                ("How do I return a battery?", "Visit any WEZU station, scan the return QR code, and place the battery in an empty slot. The slot will lock and your rental will end automatically. Charges are calculated based on actual usage time.", "getting_started", True, 134, 12),
                
                # Technical
                ("My battery is not charging. What should I do?", "Try these steps:\n1. Check if the charging cable is properly connected\n2. Ensure the power outlet is working\n3. Wait 5 minutes and try again\n4. If the issue persists, check the battery health in the app\n5. Contact support if battery health is below 60%", "technical", True, 201, 15),
                ("What is the range of WEZU batteries?", "Battery range depends on the model:\n• 48V Standard: 40-50 km\n• 48V Premium: 55-70 km\n• 60V Pro: 70-90 km\n\nActual range may vary based on terrain, rider weight, and driving style.", "technical", True, 178, 7),
                ("How to check battery health?", "Open the WEZU app → Go to 'My Rentals' → Tap on the active rental → Scroll to 'Battery Health'. You'll see SoC (State of Charge), SoH (State of Health), voltage, and temperature readings.", "technical", True, 92, 5),
                
                # Billing
                ("How are rental charges calculated?", "Charges are based on:\n• Time duration (hourly/daily/weekly/monthly rates)\n• Battery model selected\n• Subscription plan (if any)\n\nYou only pay for the time you use. Returns are pro-rated to the nearest hour.", "billing", True, 245, 18),
                ("How to get a refund?", "Refunds are processed automatically for:\n• Cancelled rentals (within 1 hour)\n• Defective batteries\n• Overcharges\n\nRefunds take 3-5 business days. Check status in App → Settings → Payment History.", "billing", True, 167, 9),
                ("What are late return fees?", "Late fees are charged as follows:\n• First 30 min: No charge (grace period)\n• 30 min - 2 hours: ₹50\n• 2 - 6 hours: ₹150\n• 6 - 24 hours: ₹300\n• Beyond 24 hours: ₹300/day\n\nFees can be waived for emergencies by contacting support.", "billing", True, 312, 22),
                
                # Account
                ("How to reset my password?", "1. Go to the login screen\n2. Tap 'Forgot Password'\n3. Enter your registered email or phone\n4. You'll receive an OTP\n5. Enter OTP and set new password\n\nPasswords must be 8+ characters with at least one number and special character.", "account", True, 87, 4),
                ("How to update KYC documents?", "Go to App → Profile → KYC Documents → Upload/Update. Required documents:\n• Aadhaar Card (front & back)\n• Driving License\n• PAN Card (optional)\n\nVerification typically takes 24-48 hours.", "account", True, 56, 2),
                
                # Dealer
                ("How to become a WEZU dealer?", "Visit our dealer portal at dealers.wezu.com and apply:\n1. Fill in business details\n2. Upload required documents (GST, Shop license)\n3. Complete video KYC\n4. Pay security deposit\n5. Get station installed within 7-10 days\n\nCommission: 8-15% on all rentals at your station.", "dealer", True, 134, 11),
                ("How is dealer commission calculated?", "Commission is based on your tier:\n• Bronze (0-50 rentals/month): 8%\n• Silver (51-150 rentals/month): 10%\n• Gold (151-300 rentals/month): 12%\n• Platinum (300+ rentals/month): 15%\n\nSettlements are processed monthly on the 5th.", "dealer", True, 98, 6),
                
                # Safety
                ("Battery safety guidelines", "• Never expose to extreme heat (>45°C) or cold (<5°C)\n• Do not charge unattended overnight\n• Keep away from water and moisture\n• Use only WEZU-approved chargers\n• If swelling or unusual smell, stop use immediately and contact support\n• Do not attempt to open or modify the battery", "safety", True, 223, 3),
                ("What to do in case of battery emergency?", "1. STOP using the battery immediately\n2. Move away if you notice smoke or unusual heat\n3. Call WEZU Emergency: 1800-XXX-XXXX\n4. Do NOT try to extinguish lithium battery fires with water\n5. Wait for our emergency response team", "safety", True, 189, 1),
                
                # Subscription
                ("What subscription plans are available?", "WEZU offers 3 plans:\n\n**Basic** - ₹999/month\n• 4 hours daily usage\n• Standard batteries only\n• Email support\n\n**Premium** - ₹1,999/month\n• Unlimited usage\n• All battery models\n• Priority support\n\n**Enterprise** - Custom pricing\n• Fleet management\n• Dedicated account manager\n• API access", "subscription", True, 156, 8),
                ("How to cancel my subscription?", "Go to App → Settings → Subscription → Cancel Plan. Note:\n• Cancel before 25th to avoid next month's charge\n• Active rentals must be returned first\n• Refund for unused days is processed within 7 days\n• You can re-subscribe anytime", "subscription", True, 78, 5),
            ]
            
            for question, answer, category, active, helpful, not_helpful in kb_articles:
                faq = FAQ(
                    question=question,
                    answer=answer,
                    category=category,
                    is_active=active,
                    helpful_count=helpful,
                    not_helpful_count=not_helpful,
                    created_at=random_date(90),
                )
                db.add(faq)
            db.commit()
            print(f"  ✓ Created {len(kb_articles)} knowledge base articles")

        print("\n✅ Support module seeding complete!")


if __name__ == "__main__":
    seed_support()
