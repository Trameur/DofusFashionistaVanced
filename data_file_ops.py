import os
import platform
import time


def replace_file(source, destination, timeout=15):
    deadline = time.monotonic() + timeout
    notified = False
    while True:
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if platform.system() != 'Windows' or time.monotonic() >= deadline:
                raise
            if not notified:
                print('File replacement temporarily blocked; retrying: %s' % destination, flush=True)
                notified = True
            time.sleep(min(1, max(0, deadline - time.monotonic())))
