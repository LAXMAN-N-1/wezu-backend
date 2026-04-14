"""Add performance indexes - Phase 11

Adds missing indexes on hot FK/filter columns identified during deep
performance audit:
  - rentals.start_station_id
  - stations.dealer_id
  - dealer_profiles.user_id (unique already, explicit index)
  - dealer_documents.dealer_id
  - dealer_applications.dealer_id (unique already, explicit index)
  - commission_logs.dealer_id
  - commission_logs.status

Revision ID: perf_indexes_ph11
Revises: (auto-detect)
"""
from alembic import op

revision = "perf_indexes_ph11"
down_revision = "b2c3d4e5f6g7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_rentals_start_station_id", "rentals", ["start_station_id"], unique=False, if_not_exists=True
    )
    op.create_index(
        "ix_stations_dealer_id", "stations", ["dealer_id"], unique=False, if_not_exists=True
    )
    op.create_index(
        "ix_dealer_profiles_user_id", "dealer_profiles", ["user_id"], unique=True, if_not_exists=True
    )
    op.create_index(
        "ix_dealer_documents_dealer_id", "dealer_documents", ["dealer_id"], unique=False, if_not_exists=True
    )
    op.create_index(
        "ix_dealer_applications_dealer_id", "dealer_applications", ["dealer_id"], unique=True, if_not_exists=True
    )
    op.create_index(
        "ix_commission_logs_dealer_id", "commission_logs", ["dealer_id"], unique=False, if_not_exists=True
    )
    op.create_index(
        "ix_commission_logs_status", "commission_logs", ["status"], unique=False, if_not_exists=True
    )


def downgrade() -> None:
    op.drop_index("ix_commission_logs_status", table_name="commission_logs")
    op.drop_index("ix_commission_logs_dealer_id", table_name="commission_logs")
    op.drop_index("ix_dealer_applications_dealer_id", table_name="dealer_applications")
    op.drop_index("ix_dealer_documents_dealer_id", table_name="dealer_documents")
    op.drop_index("ix_dealer_profiles_user_id", table_name="dealer_profiles")
    op.drop_index("ix_stations_dealer_id", table_name="stations")
    op.drop_index("ix_rentals_start_station_id", table_name="rentals")
