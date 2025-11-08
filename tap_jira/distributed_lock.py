import os

from contextlib import contextmanager
from logging import Logger

from pottery import Redlock
from redis import Redis


class DistributedLockError(Exception):
    """Raised when a distributed lock cannot be acquired."""

    def __init__(self, resource: str):
        self.resource = resource
        super().__init__(f"Failed to acquire lock for resource: '{resource}'")


class DistributedLock:
    """
    Redis distributed lock manager with a robust context manager.

    This manager is a wrapper around pottery's AIORedlock to provide a simple
    interface for acquiring and releasing locks.
    """

    def __init__(self, redis_url: str, logger: Logger):
        self._redis = Redis.from_url(redis_url)
        self._logger = logger

    @classmethod
    def from_env(cls, logger: Logger) -> "DistributedLock":
        redis_url = os.environ["DLOCK_URL"]

        return cls(redis_url, logger)

    @contextmanager
    def acquire(self, resource: str, timeout: int = 30):
        """
        Context manager for acquiring a Redis distributed lock.
        It will raise a `DistributedLockError` if the lock cannot be acquired.

        Args:
            resource: The unique identifier for the resource to lock.
            timeout: The lock's expiry time in seconds.

        Yields:
            Enters the context if the lock is acquired.

        Raises:
            DistributedLockError: If the lock could not be acquired.
        """

        lock = Redlock(
            key=resource,
            masters={self._redis},
            auto_release_time=timeout,
        )

        try:
            acquired = lock.acquire()
            if not acquired:
                raise DistributedLockError(resource)
        except Exception as e:
            self._logger.warning(
                "Failed to acquire Redis lock for resource: '%s': %s",
                resource,
                str(e),
            )

            raise DistributedLockError(resource) from e

        try:
            yield
        finally:
            if lock.locked():
                lock.release()

    def destroy(self):
        """Clean up the underlying Redis connection."""

        self._redis.close()
