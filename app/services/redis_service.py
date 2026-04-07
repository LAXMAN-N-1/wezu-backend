import redis
import time
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class RedisService:
    _pool = None
    _client = None
    _retry_after_ts = 0.0
    _retry_cooldown_seconds = 30.0

    @classmethod
    def get_client(cls):
        now = time.monotonic()
        if now < cls._retry_after_ts:
            return None

        if cls._client is None:
            try:
                if cls._pool is None:
                    cls._pool = redis.ConnectionPool.from_url(
                        settings.REDIS_URL,
                        decode_responses=True,
                        socket_connect_timeout=1,
                        socket_timeout=1,
                        health_check_interval=30,
                        max_connections=100
                    )
                cls._client = redis.Redis(connection_pool=cls._pool)
                cls._client.ping()
            except Exception as e:
                cls._client = None
                cls._retry_after_ts = now + cls._retry_cooldown_seconds
                logger.warning(f"Failed to connect to Redis (retrying in 30s): {e}")
                return None
        return cls._client

    @classmethod
    def blacklist_token(cls, token: str, ttl: int):
        """
        Blacklist a JWT token by storing it in Redis with an expiration time.
        :param token: The JWT token string
        :param ttl: Time to live in seconds (remaining validity of the token)
        """
        client = cls.get_client()
        if client and ttl > 0:
            try:
                # Key format: blacklist:token_string
                key = f"blacklist:{token}"
                client.setex(key, ttl, "blacklisted")
            except Exception as e:
                logger.error(f"Failed to blacklist token in Redis: {e}")

    @classmethod
    def is_token_blacklisted(cls, token: str) -> bool:
        """
        Check if a token is in the blacklist.
        :param token: The JWT token string
        :return: True if blacklisted, False otherwise
        """
        client = cls.get_client()
        if not client:
            return False # Fail open if Redis is down? Or fail closed? 
                         # Typically for logout we might fail open to avoid blocking legitimate users if cache extends,
                         # but for security we should probably log error. 
                         # Here we return False but log error in get_client.
        
        try:
            key = f"blacklist:{token}"
            return bool(client.exists(key))
        except Exception as e:
            cls._client = None
            cls._retry_after_ts = time.monotonic() + cls._retry_cooldown_seconds
            logger.warning(f"Failed to check token blacklist in Redis (retrying in 30s): {e}")
            return False
