import amqp_worker
import os
import shutil
import tempfile
import transaction
from nudibranch.models import File, Session, Submission, initialize_sql
from sqlalchemy import engine_from_config

BASE_FILE_PATH = None
PRIVATE_KEY_FILE = None


def complete_file(func):
    def wrapped(submission_id, complete_file, user, host, remote_dir):
        prev_cwd = os.getcwd()
        new_cwd = tempfile.mkdtemp()
        os.chdir(new_cwd)
        try:
            retval = func(submission_id, user, host, remote_dir)
        finally:
            shutil.rmtree(new_cwd)
            os.chdir(prev_cwd)
        complete_file = os.path.join(remote_dir, complete_file)
        command = 'echo -n {0} | ssh -i {1} {2}@{3} tee -a {4}'.format(
            submission_id, PRIVATE_KEY_FILE, user, host, complete_file)
        os.system(command)
        return retval
    return wrapped


def fetch_results():
    start_communicator('queue_fetch_results', fetch_results_worker)


@complete_file
def fetch_results_worker(submission_id, user, host, remote_dir):
    session = Session()
    submission = Submission.fetch_by_id(submission_id)
    if not submission:
        raise Exception('Invalid submission id: {0}'.format(submission_id))

    # Rsync to retrieve results
    cmd = 'rsync -e \'ssh -i {0}\' -rLpv {1}@{2}:{3} .'.format(
        PRIVATE_KEY_FILE, user, host, os.path.join(remote_dir, 'results/'))
    os.system(cmd)

    print os.listdir('.')

    # Store Makefile results
    if os.path.isfile('make'):
        submission.update_makefile_results(open('make').read().decode('utf-8'))
    session.add(submission)
    transaction.commit()


def start_communicator(queue_conf, work_func):
    global BASE_FILE_PATH, PRIVATE_KEY_FILE
    parser = amqp_worker.base_argument_parser()
    args, settings = amqp_worker.parse_base_args(parser, 'app:main')
    BASE_FILE_PATH = settings['file_directory']
    PRIVATE_KEY_FILE = settings['ssh_priv_key']

    engine = engine_from_config(settings, 'sqlalchemy.')
    initialize_sql(engine)

    worker = amqp_worker.AMQPWorker(settings['queue_server'],
                                    settings[queue_conf], work_func,
                                    is_daemon=args.daemon)
    worker.start()


def sync_files():
    start_communicator('queue_sync_files', sync_files_worker)


@complete_file
def sync_files_worker(submission_id, user, host, remote_dir):
    submission = Submission.fetch_by_id(submission_id)
    if not submission:
        raise Exception('Invalid submission id: {0}'.format(submission_id))

    project = submission.project

    # Make symlinks for all submission files to src directory
    os.mkdir('src')
    for file_assoc in submission.files:
        source = File.file_path(BASE_FILE_PATH, file_assoc.file.sha1)
        os.symlink(source, os.path.join('src', file_assoc.filename))

    # Copy Makefile to current directory
    if project.makefile:
        source = File.file_path(BASE_FILE_PATH, project.makefile.sha1)
        os.symlink(source, 'Makefile')

    # Rsync files
    cmd = 'rsync -e \'ssh -i {0}\' -rLpv . {1}@{2}:{3}'.format(
        PRIVATE_KEY_FILE, user, host, remote_dir)
    os.system(cmd)
