import amqp_worker
import json
import os
import shutil
import tempfile
import transaction
import pickle
from nudibranch.models import (File, Session, Submission, TestCase,
                               TestCaseResult, initialize_sql)
from nudibranch.diff_unit import DiffUnit
from nudibranch.helpers import readlines
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

    # Store test case results
    if os.path.isfile('test_cases'):
        data = json.load(open('test_cases'))
        for test_case_id, results in data.items():
            test_case_id = int(test_case_id)  # json doesn't support int keys
            try:
                update_or_create_result(submission_id, test_case_id, results)
            except Exception:
                import traceback
                traceback.print_exc()
                raise
    session = Session()
    session.add(submission)
    transaction.commit()


def update_or_create_result(submission_id, test_case_id, results):
    test_case_result = TestCaseResult.fetch_by_ids(submission_id, test_case_id)
    if test_case_result:
        test_case_result.update(results)
    else:
        results['submission_id'] = submission_id
        results['test_case_id'] = test_case_id
        test_case_result = TestCaseResult(**results)

    # get the expected output
    test_case = TestCase.fetch_by_id(test_case_result.test_case_id)
    if not test_case:
        raise Exception(
            'Invalid test case id: {0}'.format(test_case_result.test_case_id))

    expected_path = File.file_path(BASE_FILE_PATH,
                                   test_case.expected.sha1)
    expected_output = readlines(expected_path)

    # get the actual output
    # actual_path = os.path.join(worker.RESULTS_PATH,
    #                            'tc_{0}'.format(test_case_id))
    actual_path = 'tc_{0}'.format(test_case_id)
    actual_output = readlines(actual_path)

    # put them into a DiffUnit
    unit = DiffUnit(expected_output,
                    actual_output,
                    test_case_id,  # probably a better way
                    test_case.name,
                    test_case.points)

    # dump it to a file in the same way as originally, and do it as
    # a string
    diff_file = File.fetch_or_create(pickle.dumps(unit), BASE_FILE_PATH)
    test_case_result.diff = diff_file

    # data = open('tc_{}'.format(test_case_id)).read()
    # file = File.fetch_or_create(data, BASE_FILE_PATH)
    # test_case.diff = file

    session = Session()
    session.add(test_case_result)
    return test_case_result


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

    # Symlink Makefile to current directory
    if project.makefile:
        source = File.file_path(BASE_FILE_PATH, project.makefile.sha1)
        os.symlink(source, 'Makefile')

    # Symlink test inputs and copy build test case specifications
    os.mkdir('inputs')
    test_cases = []
    for test_case in project.test_cases:
        test_cases.append(test_case.serialize())
        if test_case.stdin:
            destination = os.path.join('inputs', test_case.stdin.sha1)
            if not os.path.isfile(destination):
                source = File.file_path(BASE_FILE_PATH, test_case.stdin.sha1)
                os.symlink(source, destination)

    # Save test case specification
    with open('test_cases', 'w') as fp:
        json.dump(test_cases, fp)

    # Rsync files
    cmd = 'rsync -e \'ssh -i {0}\' -rLpv . {1}@{2}:{3}'.format(
        PRIVATE_KEY_FILE, user, host, remote_dir)
    os.system(cmd)
