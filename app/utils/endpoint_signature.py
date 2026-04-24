from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, Tuple, get_type_hints


def _resolve_type_hints_safe(func: Callable[..., Any]) -> Dict[str, Any]:
    globals_ns = getattr(func, "__globals__", {})
    try:
        return get_type_hints(func, globalns=globals_ns, localns=globals_ns, include_extras=True)
    except Exception:
        resolved: Dict[str, Any] = {}
        signature = inspect.signature(func)

        for param in signature.parameters.values():
            annotation = param.annotation
            if not isinstance(annotation, str):
                continue
            try:
                resolved[param.name] = eval(annotation, globals_ns, globals_ns)
            except Exception:
                continue

        return_annotation = signature.return_annotation
        if isinstance(return_annotation, str):
            try:
                resolved["return"] = eval(return_annotation, globals_ns, globals_ns)
            except Exception:
                pass

        return resolved


def resolve_endpoint_signature(func: Callable[..., Any]) -> Tuple[inspect.Signature, Dict[str, Any]]:
    signature = inspect.signature(func)
    resolved_hints = _resolve_type_hints_safe(func)

    resolved_params = []
    for param in signature.parameters.values():
        resolved_annotation = resolved_hints.get(param.name, param.annotation)
        resolved_params.append(param.replace(annotation=resolved_annotation))

    resolved_return = resolved_hints.get("return", signature.return_annotation)
    resolved_signature = signature.replace(parameters=resolved_params, return_annotation=resolved_return)
    return resolved_signature, resolved_hints


def preserve_endpoint_signature(wrapper: Callable[..., Any], original: Callable[..., Any]) -> Callable[..., Any]:
    resolved_signature, _ = resolve_endpoint_signature(original)
    wrapper.__signature__ = resolved_signature

    annotations: Dict[str, Any] = {
        param.name: param.annotation
        for param in resolved_signature.parameters.values()
        if param.annotation is not inspect.Signature.empty
    }
    if resolved_signature.return_annotation is not inspect.Signature.empty:
        annotations["return"] = resolved_signature.return_annotation
    wrapper.__annotations__ = annotations
    return wrapper
