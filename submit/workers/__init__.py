from datetime import datetime
from functools import wraps
import os
import shutil
import tempfile
import transaction

BASE_FILE_PATH = None


def log_msg(msg):
    print('{} {}'.format(datetime.now(), msg))


def wrapper(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        # Create temporary directory
        prev_cwd = os.getcwd()
        new_cwd = tempfile.mkdtemp()
        os.chdir(new_cwd)
        try:
            retval = func(*args, **kwargs)
            transaction.commit()
        except:
            transaction.abort()
            raise
        finally:
            # Remove temporary directory
            shutil.rmtree(new_cwd)
            os.chdir(prev_cwd)
        return retval
    return wrapped
