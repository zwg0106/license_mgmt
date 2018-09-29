import os
import logging
from gevent.fileobject import FileObjectThread

LOG_FILENAME_DEFAULT = "/var/log/lic_mgmt.log"

def get_logger(name, args=None):
    """Set up the logging."""

    fmt = ("%(asctime)s %(levelname)8s [%(name)8s] %(message)s")
    datefmt = '%Y-%m-%d %H:%M:%S'

    # Log to a file
    if args is None:
        log_path = LOG_FILENAME_DEFAULT
    else:
        # TBD
        return

    path_exists = os.path.isfile(log_path)

    logging.basicConfig(level=logging.DEBUG, format=fmt, datefmt=datefmt, filename=log_path, filemode='w')

    file_handler = logging.StreamHandler()
    # file_handler = logging.FileHandler(filename=log_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(fmt))
    logging.getLogger(name).addHandler(file_handler)

    return logging.getLogger(name)


def file_stream(path, chunk_size=10 * 1024):
    with open(path, 'rb') as src:
        wrapper = FileObjectThread(src, 'rb')

        while True:
            data = wrapper.read(chunk_size)
            if not data:
                return

            yield data
