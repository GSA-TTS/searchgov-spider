import logging
import os

from redis import Redis

log = logging.getLogger(__name__)


def get_redis_connection_args(db: int = 1) -> dict:
    """Get the Redis connection arguments from environment variables."""
    return {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", "6379")),
        "db": db,  # The searchgov app uses db 0
    }


def init_redis_client(**extra_args) -> Redis:
    """Initialize a Redis client using connection arguments from environment variables."""
    # Create a Redis client with the connection arguments
    redis_connection_args = get_redis_connection_args()
    redis_connection_args.update(extra_args)
    log.debug("Attempting conection to redis with args %s", redis_connection_args)

    return Redis(**redis_connection_args)
