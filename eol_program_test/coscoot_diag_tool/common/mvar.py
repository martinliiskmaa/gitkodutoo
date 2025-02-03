import threading


class LockableBoolean:
    """
    Thread-safe boolean class
    """

    # [START __init__]
    def __init__(self, initial_value: bool = False):
        self.lock = threading.RLock()
        self.state: bool = initial_value

    # [END __init__]

    def set(self, new_value: bool = True):
        self.lock.acquire(True)
        self.state = new_value
        self.lock.release()

    def clear(self):
        self.lock.acquire(True)
        self.state = False
        self.lock.release()

    def get(self) -> bool:
        self.lock.acquire(True)
        value = self.state
        self.lock.release()
        return value
