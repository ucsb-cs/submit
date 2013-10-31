from .exceptions import HandledError, OutOfSync
from functools import wraps
import os
import shutil
import subprocess
import tempfile
import transaction

BASE_FILE_PATH = None
PRIVATE_KEY_FILE = None


def complete_file(func):
    @wraps(func)
    def wrapped(complete_file, host, remote_dir, submission_id, testable_id,
                user, **kwargs):
        prev_cwd = os.getcwd()
        new_cwd = tempfile.mkdtemp()
        os.chdir(new_cwd)
        try:
            retval = func(submission_id, testable_id, user, host, remote_dir,
                          **kwargs)
        except OutOfSync as exc:
            print('Out of Sync: {0}'.format(exc))
            return
        except HandledError as exc:
            print('Other handled error: {0}'.format(exc))
            return
        finally:
            shutil.rmtree(new_cwd)
            os.chdir(prev_cwd)
        complete_file = os.path.join(remote_dir, complete_file)
        cmd = 'echo -n {0}.{1} | ssh -i {2} {3}@{4} tee -a {5}'.format(
            submission_id, testable_id, PRIVATE_KEY_FILE, user, host,
            complete_file)
        subprocess.check_call(cmd, stdout=open(os.devnull, 'w'), shell=True)
        print('Success: submission: {0} testable: {1}'.format(submission_id,
                                                              testable_id))
        return retval
    return wrapped


def transaction_wrapper(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        try:
            retval = func(*args, **kwargs)
            transaction.commit()
        except:
            transaction.abort()
            raise
        return retval
    return wrapped
