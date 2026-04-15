from __future__ import annotations

import json
import types
from typing import Any, Optional, get_args, get_origin

from fastapi import Request, Response
from fastapi.routing import APIRoute
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_JSON_METHODS = {"POST", "PUT", "PATCH"}


def _extract_alias_strings(alias: Any) -> set[str]:
    if alias is None:
        return set()
    if isinstance(alias, str):
        return {alias}
    if isinstance(alias, (list, tuple, set, frozenset)):
        values: set[str] = set()
        for item in alias:
            values.update(_extract_alias_strings(item))
        return values
    choices = getattr(alias, "choices", None)
    if choices:
        values: set[str] = set()
        for item in choices:
            values.update(_extract_alias_strings(item))
        return values
    path = getattr(alias, "path", None)
    if path:
        values: set[str] = set()
        for item in path:
            values.update(_extract_alias_strings(item))
        return values
    return set()


def _extract_model_candidates(annotation: Any) -> list[type[BaseModel]]:
    if annotation is None:
        return []
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]

    origin = get_origin(annotation)
    if origin is None:
        return []

    args = get_args(annotation)
    if origin is types.UnionType or str(origin) == "typing.Union":
        result: list[type[BaseModel]] = []
        for arg in args:
            result.extend(_extract_model_candidates(arg))
        return result

    if str(origin) == "typing.Annotated":
        return _extract_model_candidates(args[0] if args else None)

    if origin in (list, tuple, set, frozenset):
        return _extract_model_candidates(args[0] if args else None)

    return []


def _extract_list_item_model_candidates(annotation: Any) -> list[type[BaseModel]]:
    origin = get_origin(annotation)
    if str(origin) == "typing.Annotated":
        args = get_args(annotation)
        return _extract_list_item_model_candidates(args[0] if args else None)
    if origin in (list, tuple, set, frozenset):
        args = get_args(annotation)
        return _extract_model_candidates(args[0] if args else None)
    if origin is types.UnionType or str(origin) == "typing.Union":
        result: list[type[BaseModel]] = []
        for arg in get_args(annotation):
            result.extend(_extract_list_item_model_candidates(arg))
        return result
    return []


def _field_lookup(model_cls: type[BaseModel]) -> tuple[dict[str, str], dict[str, Any]]:
    lookup: dict[str, str] = {}
    fields: dict[str, Any] = getattr(model_cls, "model_fields", {})
    for field_name, field_info in fields.items():
        lookup[field_name] = field_name
        alias = getattr(field_info, "alias", None)
        if isinstance(alias, str) and alias:
            lookup[alias] = field_name
        for item in _extract_alias_strings(getattr(field_info, "validation_alias", None)):
            if item:
                lookup[item] = field_name
    return lookup, fields


def _collect_unknown_fields(
    payload: Any,
    model_cls: type[BaseModel],
    *,
    prefix: str = "",
    max_fields: int = 25,
) -> set[str]:
    if not isinstance(payload, dict):
        return set()

    lookup, fields = _field_lookup(model_cls)
    unknown: set[str] = set()
    for raw_key, raw_value in payload.items():
        canonical = lookup.get(raw_key)
        key_path = f"{prefix}{raw_key}"
        if not canonical:
            unknown.add(key_path)
            if len(unknown) >= max_fields:
                return unknown
            continue

        field_info = fields.get(canonical)
        if not field_info:
            continue

        nested_model_candidates = _extract_model_candidates(getattr(field_info, "annotation", None))
        if nested_model_candidates and isinstance(raw_value, dict):
            nested_unknown = _best_unknown_match(
                raw_value,
                nested_model_candidates,
                prefix=f"{key_path}.",
                max_fields=max_fields - len(unknown),
            )
            unknown.update(nested_unknown)
            if len(unknown) >= max_fields:
                return unknown
            continue

        list_model_candidates = _extract_list_item_model_candidates(getattr(field_info, "annotation", None))
        if list_model_candidates and isinstance(raw_value, list):
            for idx, item in enumerate(raw_value):
                if not isinstance(item, dict):
                    continue
                nested_unknown = _best_unknown_match(
                    item,
                    list_model_candidates,
                    prefix=f"{key_path}[{idx}].",
                    max_fields=max_fields - len(unknown),
                )
                unknown.update(nested_unknown)
                if len(unknown) >= max_fields:
                    return unknown
    return unknown


def _best_unknown_match(
    payload: Any,
    model_candidates: list[type[BaseModel]],
    *,
    prefix: str,
    max_fields: int,
) -> set[str]:
    if not model_candidates or max_fields <= 0:
        return set()
    scored: list[set[str]] = []
    for model_cls in model_candidates:
        scored.append(
            _collect_unknown_fields(
                payload,
                model_cls,
                prefix=prefix,
                max_fields=max_fields,
            )
        )
    scored.sort(key=len)
    return scored[0] if scored else set()


def _detect_unknown_query_params(request: Request, route: APIRoute) -> list[str]:
    incoming = set(request.query_params.keys())
    if not incoming:
        return []
    dependant = getattr(route, "dependant", None)
    if not dependant:
        return []

    allowed: set[str] = set()
    for query_param in getattr(dependant, "query_params", []):
        name = getattr(query_param, "name", None)
        alias = getattr(query_param, "alias", None)
        if name:
            allowed.add(str(name))
        if alias:
            allowed.add(str(alias))
    if not allowed:
        return []
    return sorted(incoming - allowed)


def _detect_unknown_payload_fields(
    payload: Any,
    route: APIRoute,
    *,
    max_fields: int,
) -> list[str]:
    if not isinstance(payload, dict):
        return []

    body_field = getattr(route, "body_field", None)
    annotation = getattr(body_field, "type_", None) if body_field else None
    model_candidates = _extract_model_candidates(annotation)
    if not model_candidates:
        return []

    unknown = _best_unknown_match(payload, model_candidates, prefix="", max_fields=max_fields)
    return sorted(unknown)[:max_fields]


class AnomalyLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.LOG_ANOMALY_DETECTION_ENABLED:
            return await call_next(request)

        payload: Optional[Any] = None
        method = request.method.upper()
        path = request.url.path
        content_type = (request.headers.get("content-type") or "").lower()

        if method in _JSON_METHODS and "application/json" in content_type:
            content_len = request.headers.get("content-length")
            max_body_bytes = max(1024, int(settings.LOG_ANOMALY_MAX_BODY_BYTES))
            if content_len and content_len.isdigit() and int(content_len) > max_body_bytes:
                logger.warning(
                    "anomaly.request.body_too_large_for_inspection",
                    method=method,
                    path=path,
                    content_length=int(content_len),
                    max_body_bytes=max_body_bytes,
                )
            else:
                raw_body = await request.body()
                # BaseHTTPMiddleware can consume the request stream. Re-inject the
                # buffered body so downstream handlers/dependencies can read it.
                async def _replay_body():
                    return {"type": "http.request", "body": raw_body, "more_body": False}
                request._receive = _replay_body
                if len(raw_body) > max_body_bytes:
                    logger.warning(
                        "anomaly.request.body_too_large_for_inspection",
                        method=method,
                        path=path,
                        content_length=len(raw_body),
                        max_body_bytes=max_body_bytes,
                    )
                elif raw_body:
                    try:
                        payload = json.loads(raw_body)
                    except json.JSONDecodeError as exc:
                        logger.warning(
                            "anomaly.request.malformed_json",
                            method=method,
                            path=path,
                            error=str(exc),
                        )

        response = await call_next(request)
        route = request.scope.get("route")
        if isinstance(route, APIRoute):
            unknown_query = _detect_unknown_query_params(request, route)
            if unknown_query:
                logger.warning(
                    "anomaly.request.unknown_query_params",
                    method=method,
                    path=path,
                    unknown_query_params=unknown_query,
                )

            if payload is not None:
                unknown_fields = _detect_unknown_payload_fields(
                    payload,
                    route,
                    max_fields=max(1, int(settings.LOG_ANOMALY_MAX_UNKNOWN_FIELDS)),
                )
                if unknown_fields:
                    logger.warning(
                        "anomaly.request.unknown_payload_fields",
                        method=method,
                        path=path,
                        unknown_fields=unknown_fields,
                        unknown_count=len(unknown_fields),
                    )

        if (
            settings.LOG_ANOMALY_EMPTY_SUCCESS_RESPONSE
            and response.status_code not in {204, 304}
            and 200 <= response.status_code < 300
            and method != "HEAD"
            and path not in set(settings.LOG_EXCLUDE_PATHS or [])
        ):
            content_length = response.headers.get("content-length")
            body = getattr(response, "body", None)
            is_empty_success = content_length == "0" or (isinstance(body, (bytes, bytearray)) and len(body) == 0)
            if is_empty_success:
                logger.warning(
                    "anomaly.response.empty_success_body",
                    method=method,
                    path=path,
                    status_code=response.status_code,
                )

        return response
