from __future__ import annotations
"""Master seed script for all new modules — BESS, Notifications, Audit, Settings."""
import random
from datetime import datetime, timedelta, timezone; UTC = timezone.utc
from sqlmodel import Session, select, func

from app.models.bess import BessUnit, BessEnergyLog, BessGridEvent, BessReport
from app.models.notification_admin import PushCampaign, AutomatedTrigger, NotificationLog, NotificationConfig
from app.models.audit_log import AuditLog, SecurityEvent
from app.models.system import SystemConfig, FeatureFlag
from app.models.api_key import ApiKeyConfig
from app.models.user import User


def seed_all_modules(session: Session):
    seed_bess(session)
    seed_notifications(session)
    seed_audit_security(session)
    seed_settings(session)
    session.commit()
    print("✅ All module data seeded successfully")


def seed_bess(session: Session):
    existing = session.exec(select(BessUnit)).first()
    if existing:
        print("  ⏭ BESS already seeded")
        return
    now = datetime.now(UTC)

    # Units
    units = [
        BessUnit(name="BESS Alpha", location="Station Hub - Downtown", capacity_kwh=500, current_charge_kwh=325,
                 max_power_kw=250, status="online", soc=65, soh=97.5, temperature_c=28.3, cycle_count=450,
                 manufacturer="CATL", model_number="BESS-500K", firmware_version="v2.4.1",
                 installed_at=now - timedelta(days=180), last_maintenance_at=now - timedelta(days=15)),
        BessUnit(name="BESS Beta", location="Industrial Zone East", capacity_kwh=1000, current_charge_kwh=780,
                 max_power_kw=500, status="online", soc=78, soh=95.2, temperature_c=26.1, cycle_count=320,
                 manufacturer="BYD", model_number="BESS-1000K", firmware_version="v3.1.0",
                 installed_at=now - timedelta(days=120), last_maintenance_at=now - timedelta(days=8)),
        BessUnit(name="BESS Gamma", location="Solar Farm West", capacity_kwh=750, current_charge_kwh=180,
                 max_power_kw=375, status="maintenance", soc=24, soh=92.8, temperature_c=31.5, cycle_count=680,
                 manufacturer="CATL", model_number="BESS-750K", firmware_version="v2.3.8",
                 installed_at=now - timedelta(days=365), last_maintenance_at=now - timedelta(days=2)),
    ]
    for u in units:
        session.add(u)
    session.flush()

    # Energy logs - 30 days of data, every 30 min
    sources = ["grid", "solar", "grid", "grid", "solar", "wind"]
    for unit in units:
        for day_offset in range(30):
            for hour in range(0, 24):
                for minute in [0, 30]:
                    ts = now - timedelta(days=day_offset, hours=24 - hour, minutes=60 - minute)
                    # Simulate charge during day (solar), discharge at night
                    is_charging = 6 <= hour <= 18
                    power = random.uniform(50, unit.max_power_kw * 0.6) if is_charging else -random.uniform(30, unit.max_power_kw * 0.4)
                    energy = abs(power) * 0.5  # 30-min interval
                    soc_start = random.uniform(20, 90)
                    soc_end = soc_start + (energy / unit.capacity_kwh * 100 * (1 if is_charging else -1))
                    soc_end = max(5, min(95, soc_end))
                    session.add(BessEnergyLog(
                        bess_unit_id=unit.id, timestamp=ts, power_kw=round(power, 1),
                        energy_kwh=round(energy, 2), soc_start=round(soc_start, 1), soc_end=round(soc_end, 1),
                        source=random.choice(sources), voltage=round(random.uniform(380, 420), 1),
                        current_a=round(abs(power) / 400 * 1000, 1), temperature_c=round(random.uniform(22, 35), 1),
                    ))

    # Grid events
    event_types = ["peak_shaving", "load_shifting", "frequency_regulation", "backup"]
    statuses = ["completed", "completed", "completed", "scheduled", "active"]
    for i in range(50):
        unit = random.choice(units)
        start = now - timedelta(days=random.randint(0, 29), hours=random.randint(0, 23))
        duration_h = random.uniform(0.5, 4)
        power = random.uniform(50, unit.max_power_kw * 0.8)
        energy = power * duration_h
        status = random.choice(statuses)
        session.add(BessGridEvent(
            bess_unit_id=unit.id, event_type=random.choice(event_types), status=status,
            start_time=start, end_time=start + timedelta(hours=duration_h) if status == "completed" else None,
            target_power_kw=round(power, 1), actual_power_kw=round(power * random.uniform(0.85, 1.05), 1) if status == "completed" else None,
            energy_kwh=round(energy, 1) if status == "completed" else None,
            revenue_earned=round(energy * random.uniform(2.5, 8.0), 2) if status == "completed" else None,
            grid_operator=random.choice(["State Grid Co", "National Grid", "Regional Power"]),
        ))

    # Reports
    for unit in units:
        for week in range(4):
            start = now - timedelta(weeks=week + 1)
            end = start + timedelta(weeks=1)
            charged = random.uniform(800, 3000)
            discharged = charged * random.uniform(0.85, 0.95)
            session.add(BessReport(
                bess_unit_id=unit.id, report_type="weekly", period_start=start, period_end=end,
                total_charged_kwh=round(charged, 1), total_discharged_kwh=round(discharged, 1),
                avg_efficiency=round(discharged / charged * 100, 1), peak_power_kw=round(unit.max_power_kw * random.uniform(0.7, 1.0), 1),
                avg_soc=round(random.uniform(40, 70), 1), min_soc=round(random.uniform(10, 30), 1),
                max_soc=round(random.uniform(80, 95), 1),
                revenue=round(random.uniform(5000, 20000), 2), cost=round(random.uniform(1000, 5000), 2),
                grid_events_count=random.randint(3, 15),
            ))
    print("  ✅ Seeded BESS data (3 units, energy logs, grid events, reports)")


def seed_notifications(session: Session):
    existing = session.exec(select(PushCampaign)).first()
    if existing:
        print("  ⏭ Notifications already seeded")
        return
    now = datetime.now(UTC)

    # Campaigns
    campaigns = [
        PushCampaign(title="Welcome to Wezu! 🎉", message="Your first battery swap is free. Find your nearest station now!",
                     target_segment="all", target_count=15000, channel="push", status="sent",
                     sent_at=now - timedelta(days=20), sent_count=14500, delivered_count=13800,
                     open_count=8200, click_count=3500, failed_count=700, created_by=1),
        PushCampaign(title="Weekend Special: 50% Off Swaps", message="This weekend only — get 50% off all battery swaps. Use code WEEKEND50.",
                     target_segment="active", target_count=8500, channel="push", status="sent",
                     sent_at=now - timedelta(days=10), sent_count=8200, delivered_count=7900,
                     open_count=4100, click_count=1800, failed_count=300, created_by=1),
        PushCampaign(title="Station Maintenance Notice", message="Station Downtown Hub will be undergoing maintenance on March 28. Use nearby alternatives.",
                     target_segment="custom", target_count=2500, channel="email", status="sent",
                     sent_at=now - timedelta(days=5), sent_count=2500, delivered_count=2400,
                     open_count=1200, click_count=450, failed_count=100, created_by=1),
        PushCampaign(title="New Feature: Ride Tracking", message="Track your rides and battery usage in the new Activity tab!",
                     target_segment="all", target_count=15000, channel="push", status="scheduled",
                     scheduled_at=now + timedelta(days=3), created_by=1),
        PushCampaign(title="Re-engagement: We Miss You!", message="It's been a while! Come back and get ₹100 wallet credit.",
                     target_segment="inactive", target_count=3200, channel="push", status="draft", created_by=1),
    ]
    for c in campaigns:
        session.add(c)

    # Triggers
    triggers = [
        AutomatedTrigger(name="Welcome Message", description="Send when a new user registers",
                         event_type="welcome", channel="push", template_message="Welcome to Wezu Energy! 🔋 Your first swap is on us.",
                         delay_minutes=0, is_active=True, trigger_count=5200, last_triggered_at=now - timedelta(hours=3)),
        AutomatedTrigger(name="Rental Reminder", description="Remind users 24h before rental expires",
                         event_type="rental_reminder", channel="push", template_message="Your battery rental expires tomorrow. Return or extend to avoid late fees.",
                         delay_minutes=0, is_active=True, trigger_count=12500, last_triggered_at=now - timedelta(hours=1)),
        AutomatedTrigger(name="Payment Due", description="Alert when payment is overdue",
                         event_type="payment_due", channel="sms", template_message="Your Wezu payment of {amount} is overdue. Pay now to continue service.",
                         delay_minutes=60, is_active=True, trigger_count=3400, last_triggered_at=now - timedelta(hours=6)),
        AutomatedTrigger(name="Low Battery Alert", description="Alert when rented battery < 15%",
                         event_type="low_battery", channel="push", template_message="Your battery is at {level}%. Find a swap station nearby: {station_url}",
                         delay_minutes=0, is_active=True, trigger_count=8900, last_triggered_at=now - timedelta(minutes=45)),
        AutomatedTrigger(name="Inactivity Re-engagement", description="Send after 14 days of inactivity",
                         event_type="inactivity", channel="email", template_message="We haven't seen you in a while! Here's ₹50 credit to get you back on the road.",
                         delay_minutes=20160, is_active=True, trigger_count=2100, last_triggered_at=now - timedelta(days=1)),
        AutomatedTrigger(name="Swap Complete", description="Thank user after successful swap",
                         event_type="swap_complete", channel="push", template_message="Swap complete! ✅ Your new battery is at {level}% charge. Ride safe!",
                         delay_minutes=0, is_active=False, trigger_count=25000, last_triggered_at=now - timedelta(hours=2)),
    ]
    for t in triggers:
        session.add(t)

    # Logs - get real user IDs to avoid FK violations
    user_ids = [uid for uid in session.exec(select(User.id).limit(20)).all()]
    if not user_ids:
        user_ids = [1]  # fallback
    channels = ["push", "sms", "email", "push", "push"]
    statuses = ["delivered", "delivered", "delivered", "opened", "sent", "failed"]
    for i in range(100):
        ts = now - timedelta(hours=random.randint(0, 168))
        st = random.choice(statuses)
        session.add(NotificationLog(
            user_id=random.choice(user_ids), channel=random.choice(channels),
            title=random.choice(["Swap Reminder", "Payment Received", "Welcome!", "Low Battery", "Station Alert"]),
            message="Notification message content here...",
            status=st, sent_at=ts,
            delivered_at=ts + timedelta(seconds=random.randint(1, 60)) if st in ["delivered", "opened"] else None,
            opened_at=ts + timedelta(minutes=random.randint(1, 120)) if st == "opened" else None,
            error_message="Connection timeout" if st == "failed" else None,
        ))

    # Config
    configs = [
        NotificationConfig(provider="firebase", channel="push", display_name="Firebase Cloud Messaging",
                           api_key="AIzaSyBx7k3mN9qR2tP1vX8wZ5cD6fE7gH8iJ9k", sender_id="wezu-energy-prod",
                           is_active=True, last_tested_at=now - timedelta(days=2), test_status="success"),
        NotificationConfig(provider="twilio", channel="sms", display_name="Twilio SMS",
                           api_key="SK1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p", api_secret="auth_token_here",
                           sender_id="+14155551234", is_active=True, last_tested_at=now - timedelta(days=5), test_status="success"),
        NotificationConfig(provider="sendgrid", channel="email", display_name="SendGrid Email",
                           api_key="SG.abc123def456ghi789jkl012mno345pqr", sender_id="noreply@wezu.com",
                           is_active=True, last_tested_at=now - timedelta(days=1), test_status="success"),
        NotificationConfig(provider="smtp", channel="email", display_name="SMTP Backup",
                           api_key="smtp_password_here", sender_id="alerts@wezu.com",
                           is_active=False),
    ]
    for c in configs:
        session.add(c)
    print("  ✅ Seeded notifications (5 campaigns, 6 triggers, 100 logs, 4 configs)")


def seed_audit_security(session: Session):
    existing = session.exec(select(AuditLog)).first()
    if existing:
        print("  ⏭ Audit logs already seeded")
        return
    now = datetime.now(UTC)

    actions = ["AUTH_LOGIN", "AUTH_LOGOUT", "DATA_MODIFICATION", "USER_CREATION", "PASSWORD_RESET",
               "ACCOUNT_STATUS_CHANGE", "PERMISSION_CHANGE", "FINANCIAL_TRANSACTION"]
    resources = ["USER", "BATTERY", "STATION", "WALLET", "AUTH", "RENTAL", "DEALER"]
    ips = ["192.168.1.45", "10.0.0.12", "203.0.113.55", "172.16.0.100", "198.51.100.22"]
    agents = ["Mozilla/5.0 Chrome/120", "Mozilla/5.0 Firefox/115", "Admin Portal/1.0", "API Client/2.1"]

    # Get real user IDs
    user_ids = [uid for uid in session.exec(select(User.id).limit(10)).all()]
    if not user_ids:
        user_ids = [1]

    for i in range(200):
        ts = now - timedelta(hours=random.randint(0, 720))
        action = random.choice(actions)
        session.add(AuditLog(
            user_id=random.choice(user_ids), action=action,
            resource_type=random.choice(resources), resource_id=str(random.randint(1, 500)),
            details=f"Admin performed {action.lower().replace('_', ' ')}",
            ip_address=random.choice(ips), user_agent=random.choice(agents), timestamp=ts,
        ))

    # Security events
    event_types = ["failed_login", "suspicious_ip", "api_abuse", "brute_force", "unusual_activity"]
    severities = ["low", "medium", "high", "critical"]
    for i in range(30):
        ts = now - timedelta(hours=random.randint(0, 336))
        session.add(SecurityEvent(
            event_type=random.choice(event_types),
            severity=random.choice(severities),
            details=f"Security event detected from {random.choice(ips)}",
            source_ip=random.choice(ips),
            user_id=random.choice(user_ids) if random.random() > 0.3 else None,
            timestamp=ts,
            is_resolved=random.random() > 0.4,
        ))
    print("  ✅ Seeded audit logs (200 entries) and security events (30)")


def seed_settings(session: Session):
    existing = session.exec(select(SystemConfig)).first()
    if existing:
        print("  ⏭ Settings already seeded")
        return

    # System configs
    configs = [
        SystemConfig(key="platform_name", value="Wezu Energy", description="Platform display name"),
        SystemConfig(key="platform_logo_url", value="https://wezu.com/logo.png", description="Platform logo URL"),
        SystemConfig(key="timezone", value="Asia/Kolkata", description="Default timezone"),
        SystemConfig(key="currency", value="INR", description="Default currency"),
        SystemConfig(key="currency_symbol", value="₹", description="Currency symbol"),
        SystemConfig(key="support_email", value="support@wezu.com", description="Support email address"),
        SystemConfig(key="support_phone", value="+1-800-WEZU", description="Support phone number"),
        SystemConfig(key="2fa_enabled", value="false", description="Two-factor authentication"),
        SystemConfig(key="session_timeout_minutes", value="60", description="Admin session timeout"),
        SystemConfig(key="max_login_attempts", value="5", description="Max failed login attempts"),
        SystemConfig(key="password_min_length", value="8", description="Minimum password length"),
        SystemConfig(key="password_expiry_days", value="90", description="Password expiry in days"),
        SystemConfig(key="ip_whitelist_enabled", value="false", description="IP whitelisting"),
    ]
    for c in configs:
        session.add(c)

    # Feature flags
    flags = [
        FeatureFlag(name="battery_swap_v2", is_enabled=True, rollout_percentage=100),
        FeatureFlag(name="dealer_portal", is_enabled=True, rollout_percentage=100),
        FeatureFlag(name="smart_grid_integration", is_enabled=False, rollout_percentage=0),
        FeatureFlag(name="ai_battery_prediction", is_enabled=False, rollout_percentage=0),
        FeatureFlag(name="customer_rewards_program", is_enabled=True, rollout_percentage=50),
        FeatureFlag(name="realtime_telematics", is_enabled=True, rollout_percentage=80),
        FeatureFlag(name="dark_mode", is_enabled=True, rollout_percentage=100),
        FeatureFlag(name="push_notification_v2", is_enabled=False, rollout_percentage=0),
    ]
    for f in flags:
        session.add(f)

    # API Keys
    keys = [
        ApiKeyConfig(service_name="stripe", key_name="Stripe Live Secret Key",
                     key_value="sk_live_51ABC123DEF456GHI789JKL", environment="production", is_active=True),
        ApiKeyConfig(service_name="stripe", key_name="Stripe Test Secret Key",
                     key_value="sk_test_51ABC123DEF456GHI789JKL", environment="development", is_active=True),
        ApiKeyConfig(service_name="google_maps", key_name="Google Maps API Key",
                     key_value="AIzaSyBx7k3mN9qR2tP1vX8wZ5c", environment="production", is_active=True),
        ApiKeyConfig(service_name="firebase", key_name="Firebase Server Key",
                     key_value="AAAABBBBcccc1234567890DDDD", environment="production", is_active=True),
        ApiKeyConfig(service_name="twilio", key_name="Twilio Auth Token",
                     key_value="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6", environment="production", is_active=True),
        ApiKeyConfig(service_name="sendgrid", key_name="SendGrid API Key",
                     key_value="SG.abc123def456ghi789jkl012mno345", environment="production", is_active=True),
        ApiKeyConfig(service_name="razorpay", key_name="Razorpay Key ID",
                     key_value="rzp_live_1234567890abcdef", environment="production", is_active=False),
    ]
    for k in keys:
        session.add(k)
    print("  ✅ Seeded settings (13 configs, 8 feature flags, 7 API keys)")
