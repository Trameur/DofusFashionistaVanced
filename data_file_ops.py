import os
import platform
import time

LIKELY_HOLDERS = ('a running dev server, DB Browser for SQLite, an image viewer '
                  'or the antivirus scanning it')


def replace_file(source, destination, timeout=60):
    deadline = time.monotonic() + timeout
    notified = False
    while True:
        try:
            os.replace(source, destination)
            return
        except PermissionError as exc:
            if platform.system() != 'Windows':
                raise
            if time.monotonic() >= deadline:
                raise PermissionError('Still locked after %d s, probably held open by %s: %s'
                                      % (timeout, LIKELY_HOLDERS, destination)) from exc
            if not notified:
                print('File replacement temporarily blocked (%s?); retrying for %d s: %s'
                      % (LIKELY_HOLDERS, timeout, destination), flush=True)
                notified = True
            time.sleep(min(1, max(0, deadline - time.monotonic())))
