import asyncio
from typing import Callable, Any, Hashable
from time import monotonic

_cache = {}
_lock = asyncio.Lock()
_inflight = {}

async def cached_call_async(
    namespace: str,
    *cache_parts: Hashable,
    ttl_seconds: int,
    call: Callable[[], Any],
) -> Any:
    """Async event-loop native caching to bypass Redis blocking"""
    if ttl_seconds <= 0:
        return await call()
        
    cache_key = (namespace,) + tuple(cache_parts)
    now = monotonic()
    
    # Fast path unprotected read
    cached = _cache.get(cache_key)
    if cached and cached[0] > now:
        return cached[1]
        
    async with _lock:
        # Recheck after acquiring lock
        cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]
            
        if cache_key in _inflight:
            fut = _inflight[cache_key]
        else:
            fut = asyncio.Future()
            _inflight[cache_key] = fut
            
            try:
                # Release lock while running the expensive DB query!
                pass 
            except Exception:
                pass
                
    # If we didn't create the future, we wait for it
    if cache_key in _inflight and _inflight[cache_key] is not fut:
        return await fut
        
    # We are the leader calculating
    try:
        result = await call()
        _cache[cache_key] = (monotonic() + ttl_seconds, result)
        fut.set_result(result)
        return result
    except Exception as e:
        fut.set_exception(e)
        raise
    finally:
        async with _lock:
            _inflight.pop(cache_key, None)
