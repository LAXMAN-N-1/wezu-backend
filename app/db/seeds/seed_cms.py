"""Seed CMS data: blogs, FAQs, banners, legal documents, media assets."""
from datetime import datetime, UTC, timedelta
from sqlmodel import Session, select
from app.models.blog import Blog
from app.models.faq import FAQ
from app.models.banner import Banner
from app.models.legal import LegalDocument
from app.models.media import MediaAsset


def seed_cms(session: Session):
    """Seed all CMS tables with realistic data."""
    _seed_blogs(session)
    _seed_faqs(session)
    _seed_banners(session)
    _seed_legal(session)
    _seed_media(session)
    session.commit()
    print("✅ CMS data seeded successfully")


def _seed_blogs(session: Session):
    existing = session.exec(select(Blog)).first()
    if existing:
        print("  ⏭ Blogs already seeded")
        return

    now = datetime.now(UTC)
    blogs = [
        Blog(title="Introducing Wezu Energy's Battery Swap Network", slug="introducing-wezu-swap-network",
             content="<p>We're excited to announce the launch of our battery swap network across major cities...</p><p>With over 50 stations deployed, EV riders can now swap batteries in under 60 seconds.</p>",
             summary="Learn about our revolutionary battery swap network for electric vehicles.",
             featured_image_url="https://images.unsplash.com/photo-1593941707882-a5bba14938c7?w=800",
             category="news", author_id=1, status="published", views_count=1250,
             published_at=now - timedelta(days=30), created_at=now - timedelta(days=30), updated_at=now - timedelta(days=5)),
        Blog(title="How Battery Swapping Reduces Range Anxiety", slug="battery-swapping-range-anxiety",
             content="<p>Range anxiety is the #1 barrier to EV adoption. Battery swapping eliminates this...</p>",
             summary="Discover how battery swap technology eliminates range anxiety for EV owners.",
             featured_image_url="https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=800",
             category="educational", author_id=1, status="published", views_count=890,
             published_at=now - timedelta(days=25), created_at=now - timedelta(days=25), updated_at=now - timedelta(days=10)),
        Blog(title="BESS Technology: The Backbone of Modern Energy", slug="bess-technology-backbone",
             content="<p>Battery Energy Storage Systems (BESS) are revolutionizing how we store and distribute energy...</p>",
             summary="A deep dive into BESS technology and its role in sustainable energy infrastructure.",
             featured_image_url="https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=800",
             category="educational", author_id=1, status="published", views_count=670,
             published_at=now - timedelta(days=20), created_at=now - timedelta(days=20), updated_at=now - timedelta(days=8)),
        Blog(title="Q1 2026: Station Expansion Update", slug="q1-2026-station-expansion",
             content="<p>We've expanded to 15 new locations in Q1, bringing our total to 65 active stations...</p>",
             summary="Our quarterly update on station deployments and network growth.",
             featured_image_url="https://images.unsplash.com/photo-1497435334941-8c899ee9e8e9?w=800",
             category="update", author_id=1, status="published", views_count=430,
             published_at=now - timedelta(days=15), created_at=now - timedelta(days=15), updated_at=now - timedelta(days=3)),
        Blog(title="Safety Standards in Li-ion Battery Management", slug="safety-standards-li-ion",
             content="<p>Safety is paramount. Our batteries undergo 12 checkpoint inspections before deployment...</p>",
             summary="Understanding the rigorous safety protocols behind our battery management system.",
             featured_image_url="https://images.unsplash.com/photo-1620714223084-8fcacc6dfd8d?w=800",
             category="educational", author_id=1, status="published", views_count=320,
             published_at=now - timedelta(days=10), created_at=now - timedelta(days=10), updated_at=now - timedelta(days=2)),
        Blog(title="Dealer Partnership Program Launch", slug="dealer-partnership-program",
             content="<p>We're launching our dealer partnership program to accelerate station deployments...</p>",
             summary="Join our dealer network and be part of the EV revolution.",
             featured_image_url="https://images.unsplash.com/photo-1560472354-b33ff0c44a43?w=800",
             category="news", author_id=1, status="published", views_count=560,
             published_at=now - timedelta(days=5), created_at=now - timedelta(days=5), updated_at=now - timedelta(days=1)),
        Blog(title="Upcoming: Smart Grid Integration Features", slug="smart-grid-integration-upcoming",
             content="<p>We're developing advanced grid integration features for our BESS units...</p>",
             summary="Preview of our upcoming smart grid integration and peak-shaving capabilities.",
             category="update", author_id=1, status="draft", views_count=0,
             created_at=now - timedelta(days=2), updated_at=now - timedelta(days=1)),
        Blog(title="The Economics of Battery Swapping vs Charging", slug="economics-swapping-vs-charging",
             content="<p>A comprehensive analysis comparing battery swapping economics with traditional charging...</p>",
             summary="Cost comparison between battery swapping and traditional EV charging solutions.",
             category="educational", author_id=1, status="scheduled", views_count=0,
             published_at=now + timedelta(days=5), created_at=now - timedelta(days=1), updated_at=now),
    ]
    for b in blogs:
        session.add(b)
    print(f"  ✅ Seeded {len(blogs)} blog posts")


def _seed_faqs(session: Session):
    existing = session.exec(select(FAQ)).first()
    if existing:
        print("  ⏭ FAQs already seeded")
        return

    now = datetime.now(UTC)
    faqs = [
        FAQ(question="How does battery swapping work?", answer="Simply ride to any Wezu station, return your depleted battery, and pick up a fully charged one. The entire process takes under 60 seconds.",
            category="general", is_active=True, helpful_count=145, not_helpful_count=3, created_at=now - timedelta(days=60)),
        FAQ(question="How much does a battery swap cost?", answer="Each swap costs ₹49. Monthly unlimited plans start at ₹999/month for up to 30 swaps.",
            category="payment", is_active=True, helpful_count=230, not_helpful_count=8, created_at=now - timedelta(days=55)),
        FAQ(question="Which vehicles are compatible?", answer="Our batteries are compatible with all major electric 2-wheeler brands including Ather, Ola Electric, TVS iQube, and Bajaj Chetak.",
            category="general", is_active=True, helpful_count=180, not_helpful_count=12, created_at=now - timedelta(days=50)),
        FAQ(question="How do I find the nearest swap station?", answer="Use the Wezu app to view real-time station locations, battery availability, and navigate to the nearest station.",
            category="general", is_active=True, helpful_count=95, not_helpful_count=2, created_at=now - timedelta(days=45)),
        FAQ(question="What if a battery is defective?", answer="All batteries undergo automated health checks before and after each swap. If any issue is detected, the battery is flagged and removed from circulation immediately.",
            category="general", is_active=True, helpful_count=67, not_helpful_count=5, created_at=now - timedelta(days=40)),
        FAQ(question="How do I get a refund?", answer="Refunds are processed within 5-7 business days to your original payment method. Contact support or use the app's refund request feature.",
            category="payment", is_active=True, helpful_count=110, not_helpful_count=15, created_at=now - timedelta(days=35)),
        FAQ(question="Can I pause my subscription?", answer="Yes, you can pause your subscription for up to 30 days per billing cycle through the app settings.",
            category="rental", is_active=True, helpful_count=88, not_helpful_count=4, created_at=now - timedelta(days=30)),
        FAQ(question="How is battery health monitored?", answer="Each battery has an IoT module that monitors voltage, temperature, charge cycles, and state of health in real-time.",
            category="general", is_active=True, helpful_count=56, not_helpful_count=1, created_at=now - timedelta(days=28)),
        FAQ(question="What payment methods do you accept?", answer="We accept all major credit/debit cards, UPI, net banking, and Wezu Wallet. Stripe is used for secure payment processing.",
            category="payment", is_active=True, helpful_count=130, not_helpful_count=6, created_at=now - timedelta(days=25)),
        FAQ(question="How do I become a station dealer?", answer="Visit our Dealer Portal and submit an application. Our team will review your application and contact you within 48 hours.",
            category="general", is_active=True, helpful_count=72, not_helpful_count=3, created_at=now - timedelta(days=20)),
        FAQ(question="What is the battery warranty?", answer="All Wezu batteries come with a 2-year warranty covering manufacturing defects and capacity degradation below 70% SoH.",
            category="rental", is_active=True, helpful_count=45, not_helpful_count=2, created_at=now - timedelta(days=15)),
        FAQ(question="How do I contact support?", answer="You can reach our 24/7 support team via in-app chat, email at support@wezu.com, or call +1-800-WEZU-HELP.",
            category="general", is_active=True, helpful_count=200, not_helpful_count=10, created_at=now - timedelta(days=10)),
        FAQ(question="Are there late fees for overdue rentals?", answer="Yes, a late fee of ₹50/day is applied after the rental period ends. You'll receive reminders before the due date.",
            category="rental", is_active=True, helpful_count=95, not_helpful_count=20, created_at=now - timedelta(days=8)),
        FAQ(question="Can I track my battery's location?", answer="Yes, the app provides real-time GPS tracking for your rented battery and shows its current charge level.",
            category="general", is_active=True, helpful_count=38, not_helpful_count=1, created_at=now - timedelta(days=5)),
        FAQ(question="What happens during a power outage at a station?", answer="Our stations have backup UPS systems and BESS units that ensure continued operation during power outages for up to 4 hours.",
            category="general", is_active=True, helpful_count=25, not_helpful_count=0, created_at=now - timedelta(days=2)),
    ]
    for f in faqs:
        session.add(f)
    print(f"  ✅ Seeded {len(faqs)} FAQs")


def _seed_banners(session: Session):
    existing = session.exec(select(Banner)).first()
    if existing:
        print("  ⏭ Banners already seeded")
        return

    now = datetime.now(UTC)
    banners = [
        Banner(title="🔋 First Swap Free!", image_url="https://images.unsplash.com/photo-1593941707882-a5bba14938c7?w=1200",
               deep_link="wezu://swaps/new", priority=5, is_active=True, click_count=3200,
               start_date=now - timedelta(days=30), end_date=now + timedelta(days=30), created_at=now - timedelta(days=30)),
        Banner(title="Unlimited Monthly Plan - ₹999", image_url="https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=1200",
               deep_link="wezu://plans/monthly", priority=4, is_active=True, click_count=2100,
               start_date=now - timedelta(days=20), end_date=now + timedelta(days=40), created_at=now - timedelta(days=20)),
        Banner(title="New Stations in Your City!", image_url="https://images.unsplash.com/photo-1497435334941-8c899ee9e8e9?w=1200",
               deep_link="wezu://stations/map", priority=3, is_active=True, click_count=1500,
               start_date=now - timedelta(days=10), end_date=now + timedelta(days=60), created_at=now - timedelta(days=10)),
        Banner(title="Refer & Earn ₹200", image_url="https://images.unsplash.com/photo-1560472354-b33ff0c44a43?w=1200",
               external_url="https://wezu.com/referral", priority=2, is_active=True, click_count=890,
               start_date=now - timedelta(days=5), end_date=now + timedelta(days=90), created_at=now - timedelta(days=5)),
        Banner(title="Summer Sale - 20% Off", image_url="https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=1200",
               deep_link="wezu://offers/summer", priority=1, is_active=False, click_count=4500,
               start_date=now - timedelta(days=90), end_date=now - timedelta(days=10), created_at=now - timedelta(days=90)),
    ]
    for b in banners:
        session.add(b)
    print(f"  ✅ Seeded {len(banners)} banners")


def _seed_legal(session: Session):
    existing = session.exec(select(LegalDocument)).first()
    if existing:
        print("  ⏭ Legal docs already seeded")
        return

    now = datetime.now(UTC)
    docs = [
        LegalDocument(title="Terms of Service", slug="terms-of-service", version="2.1.0",
                      content="<h2>1. Acceptance of Terms</h2><p>By using Wezu Energy services, you agree to these terms...</p><h2>2. Service Description</h2><p>Wezu provides battery-as-a-service for electric vehicles...</p><h2>3. User Obligations</h2><p>Users must maintain batteries in good condition...</p>",
                      is_active=True, force_update=False, published_at=now - timedelta(days=90), created_at=now - timedelta(days=120)),
        LegalDocument(title="Privacy Policy", slug="privacy-policy", version="1.5.0",
                      content="<h2>1. Data Collection</h2><p>We collect personal information including name, email, phone number, and location data...</p><h2>2. Data Usage</h2><p>Your data is used to provide and improve our services...</p><h2>3. Data Protection</h2><p>We employ industry-standard encryption...</p>",
                      is_active=True, force_update=True, published_at=now - timedelta(days=60), created_at=now - timedelta(days=100)),
        LegalDocument(title="Rental Agreement", slug="rental-agreement", version="3.0.0",
                      content="<h2>1. Rental Terms</h2><p>Battery rentals are subject to the following conditions...</p><h2>2. Liability</h2><p>Users are responsible for battery damage during rental period...</p><h2>3. Return Policy</h2><p>Batteries must be returned to any Wezu station...</p>",
                      is_active=True, force_update=False, published_at=now - timedelta(days=30), created_at=now - timedelta(days=80)),
        LegalDocument(title="Cookie Policy", slug="cookie-policy", version="1.0.0",
                      content="<h2>1. What are Cookies?</h2><p>Cookies are small files stored on your device...</p><h2>2. How We Use Cookies</h2><p>We use cookies for authentication, analytics, and personalization...</p>",
                      is_active=True, force_update=False, published_at=now - timedelta(days=15), created_at=now - timedelta(days=50)),
    ]
    for d in docs:
        session.add(d)
    print(f"  ✅ Seeded {len(docs)} legal documents")


def _seed_media(session: Session):
    existing = session.exec(select(MediaAsset)).first()
    if existing:
        print("  ⏭ Media assets already seeded")
        return

    now = datetime.now(UTC)
    assets = [
        MediaAsset(file_name="wezu-logo.png", file_type="image/png", file_size_bytes=45200,
                   url="https://storage.wezu.com/uploads/wezu-logo.png", alt_text="Wezu Energy Logo",
                   category="banner", uploaded_by_id=1, created_at=now - timedelta(days=90)),
        MediaAsset(file_name="station-alpha-photo.jpg", file_type="image/jpeg", file_size_bytes=1250000,
                   url="https://storage.wezu.com/uploads/station-alpha-photo.jpg", alt_text="Station Alpha exterior",
                   category="blog", uploaded_by_id=1, created_at=now - timedelta(days=60)),
        MediaAsset(file_name="battery-48v-spec.pdf", file_type="application/pdf", file_size_bytes=890000,
                   url="https://storage.wezu.com/uploads/battery-48v-spec.pdf", alt_text="48V Battery Spec Sheet",
                   category="general", uploaded_by_id=1, created_at=now - timedelta(days=50)),
        MediaAsset(file_name="swap-tutorial.mp4", file_type="video/mp4", file_size_bytes=25600000,
                   url="https://storage.wezu.com/uploads/swap-tutorial.mp4", alt_text="Battery swap tutorial video",
                   category="blog", uploaded_by_id=1, created_at=now - timedelta(days=45)),
        MediaAsset(file_name="hero-banner-summer.jpg", file_type="image/jpeg", file_size_bytes=980000,
                   url="https://storage.wezu.com/uploads/hero-banner-summer.jpg", alt_text="Summer promo banner",
                   category="banner", uploaded_by_id=1, created_at=now - timedelta(days=40)),
        MediaAsset(file_name="dealer-brochure.pdf", file_type="application/pdf", file_size_bytes=3400000,
                   url="https://storage.wezu.com/uploads/dealer-brochure.pdf", alt_text="Dealer partnership brochure",
                   category="general", uploaded_by_id=1, created_at=now - timedelta(days=30)),
        MediaAsset(file_name="station-map-preview.png", file_type="image/png", file_size_bytes=560000,
                   url="https://storage.wezu.com/uploads/station-map-preview.png", alt_text="Station network map",
                   category="blog", uploaded_by_id=1, created_at=now - timedelta(days=20)),
        MediaAsset(file_name="app-screenshot-home.png", file_type="image/png", file_size_bytes=320000,
                   url="https://storage.wezu.com/uploads/app-screenshot-home.png", alt_text="Wezu app home screen",
                   category="banner", uploaded_by_id=1, created_at=now - timedelta(days=15)),
        MediaAsset(file_name="safety-cert.pdf", file_type="application/pdf", file_size_bytes=1200000,
                   url="https://storage.wezu.com/uploads/safety-cert.pdf", alt_text="Battery safety certification",
                   category="general", uploaded_by_id=1, created_at=now - timedelta(days=10)),
        MediaAsset(file_name="team-photo.jpg", file_type="image/jpeg", file_size_bytes=2100000,
                   url="https://storage.wezu.com/uploads/team-photo.jpg", alt_text="Wezu Energy team",
                   category="blog", uploaded_by_id=1, created_at=now - timedelta(days=5)),
    ]
    for a in assets:
        session.add(a)
    print(f"  ✅ Seeded {len(assets)} media assets")
