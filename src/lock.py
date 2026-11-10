"""A lock that works between threads AND between separate processes.

The API and the MCP server are two processes that write the same evidence and history files. A plain
threading.Lock only protects one process, so two writers could overwrite each other's update. This lock
also takes a lock on a small file, which the operating system enforces across processes.

Use it like threading.Lock: `with lock:`. It is not re-entrant, same as the lock it replaces.
"""

import threading
import time
from pathlib import Path

try:  # Windows
    import msvcrt

    def _lock_file(handle) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock_file(handle) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

except ImportError:  # macOS and Linux
    import fcntl

    def _lock_file(handle) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock_file(handle) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class InterProcessLock:
    def __init__(self, path: Path, timeout: float = 30.0):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self._thread_lock = threading.Lock()
        self._handle = None

    def __enter__(self) -> "InterProcessLock":
        self._thread_lock.acquire()
        try:
            handle = open(self.path, "a+b")
            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    _lock_file(handle)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        handle.close()
                        raise TimeoutError(f"could not get the lock {self.path} within {self.timeout}s")
                    time.sleep(0.02)
            self._handle = handle
        except BaseException:
            self._thread_lock.release()
            raise
        return self

    def __exit__(self, *exc) -> None:
        handle, self._handle = self._handle, None
        try:
            _unlock_file(handle)
        finally:
            handle.close()
            self._thread_lock.release()
