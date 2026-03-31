"""
Unit Tests for Campaign Service
Tests business logic: CRUD, targeting, frequency capping, analytics
"""
import pytest
from datetime import datetime, date, timedelta
from sqlmodel import Session
from uuid import uuid4

from app.models.campaign import (
    Campaign, CampaignTarget, CampaignSend,
    CampaignStatus, CampaignType, CampaignTargetRuleType,
)
from app.models.user import User, UserStatus
from app.models.user_profile import UserProfile
from app.models.rental import Rental, RentalStatus
from app.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignTargetRuleCreate
from app.services.campaign_service import CampaignService


# ── Fixtures ──

@pytest.fixture
def sample_user(session: Session) -> User:
    user = User(
        phone_number="9999900001",
        email="testuser@wezu.com",
        full_name="Test User",
        status=UserStatus.ACTIVE,
        last_login_at=datetime.utcnow(),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def admin_user(session: Session) -> User:
    user = User(
        phone_number="9999900000",
        email="admin@wezu.com",
        full_name="Admin User",
        status=UserStatus.ACTIVE,
        is_superuser=True,
        last_login_at=datetime.utcnow(),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def user_with_profile(session: Session) -> User:
    user = User(
        phone_number="9999900002",
        email="profile@wezu.com",
        full_name="Profile User",
        status=UserStatus.ACTIVE,
        last_login_at=datetime.utcnow(),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    profile = UserProfile(
        user_id=user.id,
        date_of_birth=date.today(),  # Birthday today for testing
        city="Mumbai",
    )
    session.add(profile)
    session.commit()
    return user


@pytest.fixture
def inactive_user(session: Session) -> User:
    user = User(
        phone_number="9999900003",
        email="inactive@wezu.com",
        full_name="Inactive User",
        status=UserStatus.ACTIVE,
        last_login_at=datetime.utcnow() - timedelta(days=60),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_draft_campaign(session: Session, admin_id: int, **kwargs) -> Campaign:
    """Helper to create a draft campaign directly."""
    defaults = {
        "name": "Test Campaign",
        "type": CampaignType.MANUAL,
        "message_title": "Hello",
        "message_body": "This is a test campaign",
        "frequency_cap": 3,
        "status": CampaignStatus.DRAFT,
        "created_by": admin_id,
    }
    defaults.update(kwargs)
    campaign = Campaign(**defaults)
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


# ── Tests ──

class TestCreateCampaign:
    def test_create_campaign_draft(self, session: Session, admin_user: User):
        payload = CampaignCreate(
            name="Summer Sale",
            type="manual",
            message_title="Summer Sale!",
            message_body="Get 20% off on all rentals",
            frequency_cap=2,
        )
        campaign = CampaignService.create_campaign(session, payload, admin_user.id)

        assert campaign.name == "Summer Sale"
        assert campaign.status == CampaignStatus.DRAFT
        assert campaign.sent_count == 0
        assert campaign.frequency_cap == 2

    def test_create_campaign_validates_frequency_cap(self, session: Session, admin_user: User):
        payload = CampaignCreate(
            name="Test",
            type="manual",
            message_title="Test",
            message_body="Test body",
            frequency_cap=3,  # max allowed is 3
        )
        campaign = CampaignService.create_campaign(session, payload, admin_user.id)
        assert campaign.frequency_cap <= 3

    def test_create_campaign_with_targets(self, session: Session, admin_user: User):
        payload = CampaignCreate(
            name="Location Campaign",
            type="manual",
            message_title="Mumbai Users",
            message_body="Special offer for Mumbai!",
            targets=[
                CampaignTargetRuleCreate(
                    rule_type="location",
                    rule_config={"city": "Mumbai"},
                ),
            ],
        )
        campaign = CampaignService.create_campaign(session, payload, admin_user.id)
        targets = session.query(CampaignTarget).filter(
            CampaignTarget.campaign_id == campaign.id
        ).all()
        assert len(targets) == 1
        assert targets[0].rule_type == CampaignTargetRuleType.LOCATION


class TestCampaignStatusTransitions:
    def test_activate_campaign_changes_status(self, session: Session, admin_user: User):
        campaign = _create_draft_campaign(
            session, admin_user.id,
            scheduled_at=datetime.utcnow() + timedelta(hours=1),
        )
        activated = CampaignService.activate_campaign(session, campaign.id)
        assert activated.status == CampaignStatus.SCHEDULED

    def test_activate_birthday_goes_active(self, session: Session, admin_user: User):
        campaign = _create_draft_campaign(
            session, admin_user.id, type=CampaignType.BIRTHDAY
        )
        activated = CampaignService.activate_campaign(session, campaign.id)
        assert activated.status == CampaignStatus.ACTIVE

    def test_activate_requires_schedule_for_non_birthday(self, session: Session, admin_user: User):
        campaign = _create_draft_campaign(session, admin_user.id, scheduled_at=None)
        with pytest.raises(Exception) as exc_info:
            CampaignService.activate_campaign(session, campaign.id)
        assert "scheduled_at" in str(exc_info.value.detail).lower() or "schedule" in str(exc_info.value.detail).lower()

    def test_pause_campaign(self, session: Session, admin_user: User):
        campaign = _create_draft_campaign(
            session, admin_user.id,
            status=CampaignStatus.ACTIVE,
        )
        paused = CampaignService.pause_campaign(session, campaign.id)
        assert paused.status == CampaignStatus.PAUSED


class TestCampaignCRUD:
    def test_delete_only_draft_or_paused(self, session: Session, admin_user: User):
        campaign = _create_draft_campaign(
            session, admin_user.id, status=CampaignStatus.ACTIVE
        )
        with pytest.raises(Exception) as exc_info:
            CampaignService.delete_campaign(session, campaign.id)
        assert "draft or paused" in str(exc_info.value.detail).lower()

    def test_delete_draft_succeeds(self, session: Session, admin_user: User):
        campaign = _create_draft_campaign(session, admin_user.id)
        result = CampaignService.delete_campaign(session, campaign.id)
        assert "deleted" in result["message"].lower()

    def test_update_only_draft_or_paused(self, session: Session, admin_user: User):
        campaign = _create_draft_campaign(
            session, admin_user.id, status=CampaignStatus.ACTIVE
        )
        payload = CampaignUpdate(name="Updated Name")
        with pytest.raises(Exception) as exc_info:
            CampaignService.update_campaign(session, campaign.id, payload)
        assert "draft or paused" in str(exc_info.value.detail).lower()

    def test_update_draft_succeeds(self, session: Session, admin_user: User):
        campaign = _create_draft_campaign(session, admin_user.id)
        payload = CampaignUpdate(name="Updated Campaign Name")
        updated = CampaignService.update_campaign(session, campaign.id, payload)
        assert updated.name == "Updated Campaign Name"


class TestFrequencyCapping:
    def test_frequency_cap_enforcement(self, session: Session, sample_user: User, admin_user: User):
        campaign = _create_draft_campaign(session, admin_user.id)

        # Add 3 sends this week
        for i in range(3):
            send = CampaignSend(
                campaign_id=campaign.id,
                user_id=sample_user.id,
                sent_at=datetime.utcnow() - timedelta(days=i),
            )
            session.add(send)
        session.commit()

        # User should be capped
        can_send = CampaignService.check_frequency_cap(session, sample_user.id, cap=3)
        assert can_send is False

    def test_frequency_cap_allows_under_limit(self, session: Session, sample_user: User, admin_user: User):
        campaign = _create_draft_campaign(session, admin_user.id)

        # Add 1 send
        send = CampaignSend(
            campaign_id=campaign.id,
            user_id=sample_user.id,
        )
        session.add(send)
        session.commit()

        can_send = CampaignService.check_frequency_cap(session, sample_user.id, cap=3)
        assert can_send is True


class TestTargeting:
    def test_birthday_targeting(self, session: Session, user_with_profile: User, admin_user: User):
        campaign = _create_draft_campaign(
            session, admin_user.id, type=CampaignType.BIRTHDAY
        )
        target = CampaignTarget(
            campaign_id=campaign.id,
            rule_type=CampaignTargetRuleType.BIRTHDAY,
            rule_config={},
        )
        session.add(target)
        session.commit()

        users = CampaignService.resolve_targets(session, campaign)
        user_ids = [u.id for u in users]
        assert user_with_profile.id in user_ids

    def test_location_targeting(self, session: Session, user_with_profile: User, admin_user: User):
        campaign = _create_draft_campaign(session, admin_user.id)
        target = CampaignTarget(
            campaign_id=campaign.id,
            rule_type=CampaignTargetRuleType.LOCATION,
            rule_config={"city": "Mumbai"},
        )
        session.add(target)
        session.commit()

        users = CampaignService.resolve_targets(session, campaign)
        user_ids = [u.id for u in users]
        assert user_with_profile.id in user_ids

    def test_last_activity_targeting(self, session: Session, inactive_user: User, admin_user: User):
        campaign = _create_draft_campaign(session, admin_user.id)
        target = CampaignTarget(
            campaign_id=campaign.id,
            rule_type=CampaignTargetRuleType.LAST_ACTIVITY,
            rule_config={"inactive_days": 30},
        )
        session.add(target)
        session.commit()

        users = CampaignService.resolve_targets(session, campaign)
        user_ids = [u.id for u in users]
        assert inactive_user.id in user_ids


class TestAnalytics:
    def test_campaign_analytics(self, session: Session, admin_user: User):
        campaign = _create_draft_campaign(
            session, admin_user.id,
            sent_count=100,
            opened_count=40,
            converted_count=10,
        )
        analytics = CampaignService.get_analytics(session, campaign.id)

        assert analytics["sent_count"] == 100
        assert analytics["opened_count"] == 40
        assert analytics["converted_count"] == 10
        assert analytics["open_rate"] == 40.0
        assert analytics["conversion_rate"] == 10.0

    def test_campaign_analytics_zero_sent(self, session: Session, admin_user: User):
        campaign = _create_draft_campaign(session, admin_user.id)
        analytics = CampaignService.get_analytics(session, campaign.id)

        assert analytics["open_rate"] == 0.0
        assert analytics["conversion_rate"] == 0.0


class TestTestSend:
    def test_send_test_to_admin(self, session: Session, admin_user: User):
        campaign = _create_draft_campaign(session, admin_user.id)
        result = CampaignService.send_test(session, campaign.id, admin_user)
        assert "test" in result["message"].lower()
