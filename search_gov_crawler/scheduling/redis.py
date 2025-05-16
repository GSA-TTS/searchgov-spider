import os

from redis import Redis


def get_redis_connection_args() -> dict:
    """Get the Redis connection arguments from environment variables."""
    return {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", "6379")),
        "db": 1,  # The searchgov app uses db 0
    }


def init_redis_client(**extra_args) -> Redis:
    """Initialize a Redis client using connection arguments from environment variables."""
    # Create a Redis client with the connection arguments
    redis_connection_args = get_redis_connection_args()
    return Redis(**redis_connection_args, **extra_args)
