"""
Real-time Logistics Order Updates API
WebSocket endpoint for push-based order state changes.
"""
from typing import Optional
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from app.api import deps
from app.core.database import engine
from app.services.websocket_service import manager

router = APIRouter()
logger = logging.getLogger(__name__)


def _normalize_token(raw_token: str) -> str:
    token = (raw_token or "").strip()
    if token.lower().startswith("bearer "):
        token = token.split(" ", 1)[1].strip()
    return token


def _authenticate_internal_operator(token: str):
    normalized = _normalize_token(token)
    if not normalized:
        raise ValueError("Missing token")
    with Session(engine) as db:
        user = deps.get_current_user(db=db, token=normalized)
        deps.require_internal_operator(db=db, current_user=user)
        return user


async def _send_auth_error_and_close(
    websocket: WebSocket,
    *,
    status_code: int,
    detail: str,
) -> None:
    close_code = 4403 if status_code == 403 else 4401
    try:
        await websocket.accept()
        await websocket.send_json(
            {
                "type": "auth_error",
                "status_code": status_code,
                "detail": detail,
            }
        )
    except Exception:
        logger.debug("Orders WebSocket auth failure frame could not be delivered")
    finally:
        try:
            await websocket.close(code=close_code, reason=detail[:123])
        except Exception:
            pass


@router.websocket("/stream")
@router.websocket("/stream/{order_id}")
async def orders_stream(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
    order_id: Optional[str] = None,
):
    """
    WebSocket endpoint for order updates.

    Examples:
    - /api/v1/orders/stream?token=<jwt>
    - /api/v1/orders/stream/ORD-5001?token=<jwt>
    """
    try:
        current_user = _authenticate_internal_operator(token)
    except HTTPException as exc:
        status_code = 403 if exc.status_code == 403 else 401
        detail = str(exc.detail or "Invalid or unauthorized token")
        await _send_auth_error_and_close(
            websocket,
            status_code=status_code,
            detail=detail,
        )
        logger.warning("Orders WebSocket auth failed: %s", exc)
        return
    except Exception as exc:
        await _send_auth_error_and_close(
            websocket,
            status_code=401,
            detail="Invalid or unauthorized token",
        )
        logger.warning("Orders WebSocket auth failed: %s", exc)
        return

    await manager.connect(websocket, current_user.id)
    try:
        if order_id:
            await manager.subscribe_order(current_user.id, str(order_id))
        else:
            await manager.subscribe_all_orders(current_user.id)

        await websocket.send_json(
            {
                "type": "orders_stream_ready",
                "timestamp": datetime.utcnow().isoformat(),
                "scope": "order" if order_id else "all",
                "order_id": str(order_id) if order_id else None,
                "supports_inventory_location_subscriptions": True,
            }
        )

        while True:
            payload = await websocket.receive_json()
            command = (payload or {}).get("command")
            if command == "ping":
                await websocket.send_json(
                    {
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
            elif command == "subscribe_order":
                target_order_id = str((payload or {}).get("order_id") or "").strip()
                if target_order_id:
                    await manager.subscribe_order(current_user.id, target_order_id)
            elif command == "unsubscribe_order":
                target_order_id = str((payload or {}).get("order_id") or "").strip()
                if target_order_id:
                    await manager.unsubscribe_order(current_user.id, target_order_id)
            elif command == "subscribe_inventory_location":
                raw_location_type = str((payload or {}).get("location_type") or "").strip()
                raw_location_id = (payload or {}).get("location_id")
                try:
                    location_id_int = int(raw_location_id)
                    subscription_key = await manager.subscribe_inventory_location(
                        current_user.id,
                        raw_location_type,
                        location_id_int,
                    )
                    await websocket.send_json(
                        {
                            "type": "inventory_subscription_ack",
                            "timestamp": datetime.utcnow().isoformat(),
                            "action": "subscribe",
                            "subscription_key": subscription_key,
                        }
                    )
                except Exception as exc:
                    await websocket.send_json(
                        {
                            "type": "inventory_subscription_error",
                            "timestamp": datetime.utcnow().isoformat(),
                            "detail": str(exc),
                        }
                    )
            elif command == "unsubscribe_inventory_location":
                raw_location_type = str((payload or {}).get("location_type") or "").strip()
                raw_location_id = (payload or {}).get("location_id")
                try:
                    location_id_int = int(raw_location_id)
                    subscription_key = await manager.unsubscribe_inventory_location(
                        current_user.id,
                        raw_location_type,
                        location_id_int,
                    )
                    await websocket.send_json(
                        {
                            "type": "inventory_subscription_ack",
                            "timestamp": datetime.utcnow().isoformat(),
                            "action": "unsubscribe",
                            "subscription_key": subscription_key,
                        }
                    )
                except Exception as exc:
                    await websocket.send_json(
                        {
                            "type": "inventory_subscription_error",
                            "timestamp": datetime.utcnow().isoformat(),
                            "detail": str(exc),
                        }
                    )
    except WebSocketDisconnect:
        manager.disconnect(websocket, current_user.id)
    except Exception as exc:
        logger.exception("Orders WebSocket runtime error: %s", exc)
        manager.disconnect(websocket, current_user.id)
        await websocket.close()
