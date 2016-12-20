import threading
import time

class MsgReader(threading.Thread):
    """
    Threaded object used for reading process output stream from dmsg.
    """

    def __init__(self, stream, queue, *args, **kwargs):
        super(MsgReader, self).__init__(*args, **kwargs)
        self._stream = stream
        self._queue = queue

        # Event used to terminate thread. This way we will have a chance to
        # tie up loose ends.
        self._stop = threading.Event()

    def stop(self):
        """
        Stop thread. Call this function to terminate the thread.
        """
        self._stop.set()

    def stopped(self):
        """
        Check whether the thread has been terminated.
        """
        return self._stop.isSet()

    def run(self):
        while True:
            # Flush buffered data (not sure this actually works?)
            self._stream.flush()

            # Read available data.
            for line in iter(self._stream.readline, b''):
                self._queue.put(line)

            # Breather.
            time.sleep(0.25)

            # Check whether thread has been terminated.
            if self.stopped():
                break