from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional, Sequence
from urllib.parse import urlsplit

from fastapi import HTTPException, status
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.core.config import settings
from app.models.passkey import PasskeyChallenge, PasskeyCredential
from app.models.user import User


class PasskeyService:
    CEREMONY_REGISTRATION = "registration"
    CEREMONY_AUTHENTICATION = "authentication"

    @classmethod
    def _clean_origin(cls, origin: str) -> str:
        value = (origin or "").strip()
        if not value:
            return ""
        if value.startswith("http://") or value.startswith("https://"):
            return value.rstrip("/")
        return value

    @classmethod
    def _rp_id_from_frontend_base(cls) -> str:
        parsed = urlsplit((settings.FRONTEND_BASE_URL or "").strip())
        return (parsed.hostname or "").strip().lower()

    @classmethod
    def get_relying_party_id(cls) -> str:
        raw_rp_id = (settings.PASSKEY_RP_ID or "").strip()
        if raw_rp_id:
            parsed = urlsplit(raw_rp_id)
            rp_id = (parsed.hostname or raw_rp_id).strip().lower()
        else:
            rp_id = cls._rp_id_from_frontend_base()

        if not rp_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Passkey RP ID is not configured",
            )

        return rp_id

    @classmethod
    def get_expected_origins(cls) -> str | list[str]:
        origins: list[str] = []
        configured_origins: list[str] = []

        for configured in settings.PASSKEY_ORIGINS:
            clean = cls._clean_origin(configured)
            if clean and clean not in configured_origins:
                configured_origins.append(clean)

        if configured_origins:
            origins.extend(configured_origins)
        else:
            frontend_origin = cls._clean_origin(settings.FRONTEND_BASE_URL)
            if frontend_origin and frontend_origin not in origins:
                origins.append(frontend_origin)

        rp_origin = f"https://{cls.get_relying_party_id()}"
        if rp_origin not in origins:
            origins.append(rp_origin)

        if not origins:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No passkey origins configured",
            )

        if len(origins) == 1:
            return origins[0]
        return origins

    @classmethod
    def _serialize_transports(cls, transports: Sequence[str] | None) -> str:
        values = [str(item).strip() for item in (transports or []) if str(item).strip()]
        return json.dumps(values)

    @classmethod
    def _deserialize_transports(cls, transports_json: Optional[str]) -> list[str]:
        if not transports_json:
            return []
        try:
            parsed = json.loads(transports_json)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            return []
        return []

    @classmethod
    def _create_challenge(
        cls,
        db: Session,
        *,
        ceremony: str,
        challenge_bytes: bytes,
        user_id: Optional[int],
    ) -> PasskeyChallenge:
        now = datetime.utcnow()
        challenge = PasskeyChallenge(
            challenge_id=uuid.uuid4().hex,
            challenge=bytes_to_base64url(challenge_bytes),
            ceremony=ceremony,
            user_id=user_id,
            created_at=now,
            expires_at=now + timedelta(seconds=settings.PASSKEY_CHALLENGE_TTL_SECONDS),
        )
        db.add(challenge)
        db.commit()
        db.refresh(challenge)
        return challenge

    @classmethod
    def _claim_challenge(
        cls,
        db: Session,
        *,
        challenge_id: str,
        ceremony: str,
        user_id: Optional[int] = None,
    ) -> PasskeyChallenge:
        now = datetime.utcnow()

        statement = (
            select(PasskeyChallenge)
            .where(PasskeyChallenge.challenge_id == challenge_id)
            .where(PasskeyChallenge.ceremony == ceremony)
            .where(PasskeyChallenge.used_at.is_(None))
            .where(PasskeyChallenge.expires_at > now)
        )
        if user_id is not None:
            statement = statement.where(PasskeyChallenge.user_id == user_id)

        challenge = db.exec(statement).first()
        if challenge is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Passkey challenge expired or invalid",
            )

        challenge.used_at = now
        db.add(challenge)
        db.commit()
        db.refresh(challenge)
        return challenge

    @classmethod
    def _build_public_key_descriptors(
        cls, passkeys: Sequence[PasskeyCredential]
    ) -> list[PublicKeyCredentialDescriptor]:
        descriptors: list[PublicKeyCredentialDescriptor] = []

        for passkey in passkeys:
            try:
                credential_bytes = base64url_to_bytes(passkey.credential_id)
            except Exception:
                continue

            transports: list[AuthenticatorTransport] = []
            for value in cls._deserialize_transports(passkey.transports_json):
                try:
                    transports.append(AuthenticatorTransport(value))
                except Exception:
                    continue

            descriptor = PublicKeyCredentialDescriptor(id=credential_bytes)
            if transports:
                descriptor.transports = transports
            descriptors.append(descriptor)

        return descriptors

    @classmethod
    def _find_user_by_username(cls, db: Session, username: str) -> Optional[User]:
        normalized = (username or "").strip()
        if not normalized:
            return None

        if "@" in normalized:
            statement = select(User).where(User.email == normalized)
        else:
            statement = select(User).where(User.phone_number == normalized)

        return db.exec(statement).first()

    @classmethod
    def get_active_passkeys_for_user(cls, db: Session, user_id: int) -> list[PasskeyCredential]:
        statement = (
            select(PasskeyCredential)
            .where(PasskeyCredential.user_id == user_id)
            .where(PasskeyCredential.is_active.is_(True))
            .order_by(PasskeyCredential.created_at.desc())
        )
        return list(db.exec(statement).all())

    @classmethod
    def generate_registration_options(
        cls,
        db: Session,
        *,
        user: User,
    ) -> dict[str, Any]:
        existing = cls.get_active_passkeys_for_user(db, user.id)
        if len(existing) >= settings.PASSKEY_MAX_CREDENTIALS_PER_USER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum number of passkeys reached for this account",
            )

        user_name = user.email or user.phone_number or f"user-{user.id}"
        user_display = user.full_name or user_name

        options = generate_registration_options(
            rp_id=cls.get_relying_party_id(),
            rp_name=settings.PASSKEY_RP_NAME,
            user_id=str(user.id).encode("utf-8"),
            user_name=user_name,
            user_display_name=user_display,
            timeout=60000,
            attestation=AttestationConveyancePreference.NONE,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
            exclude_credentials=cls._build_public_key_descriptors(existing),
        )

        challenge = cls._create_challenge(
            db,
            ceremony=cls.CEREMONY_REGISTRATION,
            challenge_bytes=options.challenge,
            user_id=user.id,
        )

        return {
            "challenge_id": challenge.challenge_id,
            "public_key": json.loads(options_to_json(options)),
            "expires_at": challenge.expires_at,
        }

    @classmethod
    def verify_registration(
        cls,
        db: Session,
        *,
        user: User,
        challenge_id: str,
        credential: dict[str, Any],
        passkey_name: Optional[str] = None,
    ) -> PasskeyCredential:
        challenge = cls._claim_challenge(
            db,
            challenge_id=challenge_id,
            ceremony=cls.CEREMONY_REGISTRATION,
            user_id=user.id,
        )

        try:
            verification = verify_registration_response(
                credential=credential,
                expected_challenge=base64url_to_bytes(challenge.challenge),
                expected_rp_id=cls.get_relying_party_id(),
                expected_origin=cls.get_expected_origins(),
                require_user_verification=True,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Passkey registration verification failed: {exc}",
            ) from exc

        credential_id = bytes_to_base64url(verification.credential_id)
        public_key = bytes_to_base64url(verification.credential_public_key)

        response_payload = credential.get("response") if isinstance(credential, dict) else None
        transports = []
        if isinstance(response_payload, dict):
            raw_transports = response_payload.get("transports")
            if isinstance(raw_transports, list):
                transports = [str(item) for item in raw_transports if item]

        existing = db.exec(
            select(PasskeyCredential).where(PasskeyCredential.credential_id == credential_id)
        ).first()

        now = datetime.utcnow()
        if existing and existing.user_id != user.id and existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This passkey is already linked to another account",
            )

        if existing is None:
            existing = PasskeyCredential(
                user_id=user.id,
                credential_id=credential_id,
                public_key=public_key,
                sign_count=verification.sign_count,
                aaguid=verification.aaguid,
                transports_json=cls._serialize_transports(transports),
                credential_device_type=verification.credential_device_type.value,
                credential_backed_up=verification.credential_backed_up,
                passkey_name=(passkey_name or "").strip() or None,
                last_used_at=now,
                is_active=True,
                revoked_at=None,
                created_at=now,
                updated_at=now,
            )
        else:
            existing.user_id = user.id
            existing.public_key = public_key
            existing.sign_count = verification.sign_count
            existing.aaguid = verification.aaguid
            if transports:
                existing.transports_json = cls._serialize_transports(transports)
            existing.credential_device_type = verification.credential_device_type.value
            existing.credential_backed_up = verification.credential_backed_up
            if passkey_name is not None:
                existing.passkey_name = (passkey_name or "").strip() or None
            existing.last_used_at = now
            existing.is_active = True
            existing.revoked_at = None
            existing.updated_at = now

        user.biometric_login_enabled = True

        db.add(existing)
        db.add(user)
        db.commit()
        db.refresh(existing)
        return existing

    @classmethod
    def generate_authentication_options(
        cls,
        db: Session,
        *,
        username: Optional[str],
    ) -> dict[str, Any]:
        allow_credentials: Optional[list[PublicKeyCredentialDescriptor]] = None
        challenge_user_id: Optional[int] = None

        normalized_username = (username or "").strip()
        if normalized_username:
            user = cls._find_user_by_username(db, normalized_username)
            if user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

            user_passkeys = cls.get_active_passkeys_for_user(db, user.id)
            if not user_passkeys:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No passkeys registered for this account",
                )

            allow_credentials = cls._build_public_key_descriptors(user_passkeys)
            challenge_user_id = user.id

        options = generate_authentication_options(
            rp_id=cls.get_relying_party_id(),
            timeout=60000,
            allow_credentials=allow_credentials,
            user_verification=UserVerificationRequirement.REQUIRED,
        )

        challenge = cls._create_challenge(
            db,
            ceremony=cls.CEREMONY_AUTHENTICATION,
            challenge_bytes=options.challenge,
            user_id=challenge_user_id,
        )

        return {
            "challenge_id": challenge.challenge_id,
            "public_key": json.loads(options_to_json(options)),
            "expires_at": challenge.expires_at,
        }

    @classmethod
    def verify_authentication(
        cls,
        db: Session,
        *,
        challenge_id: str,
        credential: dict[str, Any],
    ) -> tuple[User, PasskeyCredential]:
        challenge = cls._claim_challenge(
            db,
            challenge_id=challenge_id,
            ceremony=cls.CEREMONY_AUTHENTICATION,
        )

        credential_id = ""
        if isinstance(credential, dict):
            credential_id = (credential.get("id") or credential.get("rawId") or "").strip()

        if not credential_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passkey credential id is missing",
            )

        passkey = db.exec(
            select(PasskeyCredential)
            .where(PasskeyCredential.credential_id == credential_id)
            .where(PasskeyCredential.is_active.is_(True))
        ).first()
        if passkey is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unknown or inactive passkey",
            )

        if challenge.user_id is not None and passkey.user_id != challenge.user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Passkey is not valid for this account",
            )

        try:
            verification = verify_authentication_response(
                credential=credential,
                expected_challenge=base64url_to_bytes(challenge.challenge),
                expected_rp_id=cls.get_relying_party_id(),
                expected_origin=cls.get_expected_origins(),
                credential_public_key=base64url_to_bytes(passkey.public_key),
                credential_current_sign_count=int(passkey.sign_count or 0),
                require_user_verification=True,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Passkey authentication failed: {exc}",
            ) from exc

        user = db.exec(
            select(User)
            .where(User.id == passkey.user_id)
            .options(selectinload(User.roles))
        ).first()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

        now = datetime.utcnow()
        passkey.sign_count = int(verification.new_sign_count)
        passkey.credential_device_type = verification.credential_device_type.value
        passkey.credential_backed_up = bool(verification.credential_backed_up)
        passkey.last_used_at = now
        passkey.updated_at = now

        db.add(passkey)
        db.commit()
        db.refresh(passkey)

        return user, passkey

    @classmethod
    def list_passkeys(cls, db: Session, *, user_id: int) -> list[PasskeyCredential]:
        return cls.get_active_passkeys_for_user(db, user_id)

    @classmethod
    def deactivate_passkey(cls, db: Session, *, user_id: int, credential_id: str) -> None:
        credential = db.exec(
            select(PasskeyCredential)
            .where(PasskeyCredential.user_id == user_id)
            .where(PasskeyCredential.credential_id == credential_id)
            .where(PasskeyCredential.is_active.is_(True))
        ).first()
        if credential is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passkey not found")

        now = datetime.utcnow()
        credential.is_active = False
        credential.revoked_at = now
        credential.updated_at = now
        db.add(credential)

        remaining = db.exec(
            select(PasskeyCredential.id)
            .where(PasskeyCredential.user_id == user_id)
            .where(PasskeyCredential.is_active.is_(True))
            .limit(1)
        ).first()

        if remaining is None:
            user = db.get(User, user_id)
            if user is not None:
                user.biometric_login_enabled = False
                db.add(user)

        db.commit()
