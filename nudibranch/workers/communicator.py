import amqp_worker
import json
import os
import shutil
import subprocess
import tempfile
import transaction
import pickle
from functools import wraps
from nudibranch.models import (File, Session, Submission, TestCaseResult,
                               Testable, TestableResult, configure_sql)
from nudibranch.diff_unit import Diff
from nudibranch.helpers import readlines
from sqlalchemy import engine_from_config

BASE_FILE_PATH = None
PRIVATE_KEY_FILE = None


def complete_file(func):
    @wraps(func)
    def wrapped(complete_file, host, remote_dir, submission_id, testable_id,
                user):
        prev_cwd = os.getcwd()
        new_cwd = tempfile.mkdtemp()
        os.chdir(new_cwd)
        try:
            retval = func(submission_id, testable_id, user, host, remote_dir)
        finally:
            shutil.rmtree(new_cwd)
            os.chdir(prev_cwd)
            # Always abort
            transaction.abort()
        complete_file = os.path.join(remote_dir, complete_file)
        cmd = 'echo -n {0}.{1} | ssh -i {2} {3}@{4} tee -a {5}'.format(
            submission_id, testable_id, PRIVATE_KEY_FILE, user, host,
            complete_file)
        subprocess.check_call(cmd, stdout=open(os.devnull, 'w'), shell=True)
        print('Success: submission: {0} testable: {1}'.format(submission_id,
                                                              testable_id))
        return retval
    return wrapped


def fetch_results():
    start_communicator('fetch_results', fetch_results_worker)


@complete_file
def fetch_results_worker(submission_id, testable_id, user, host, remote_dir):
    submission = Submission.fetch_by_id(submission_id)
    if not submission:
        raise Exception('Invalid submission id: {0}'.format(submission_id))
    testable = Testable.fetch_by_id(testable_id)
    if not testable:
        raise Exception('Invalid testable id: {0}'.format(testable_id))

    # Rsync to retrieve results
    cmd = 'rsync -e \'ssh -i {0}\' -rLpv {1}@{2}:{3} .'.format(
        PRIVATE_KEY_FILE, user, host, os.path.join(remote_dir, 'results/'))
    subprocess.check_call(cmd, stdout=open(os.devnull, 'w'), shell=True)

    session = Session()

    # Store Makefile results
    if os.path.isfile('make'):
        testable_result = TestableResult.fetch_or_create(
            testable=testable, submission=submission,
            make_results=open('make').read().decode('utf-8'))
        session.add(testable_result)

    # Create dictionary of completed test_cases
    if os.path.isfile('test_cases'):
        results = dict((int(x[0]), x[1]) for x
                       in json.load(open('test_cases')).items())
    else:
        results = {}

    # Set or update relevant test case results
    for test_case in testable.test_cases:
        test_case_result = TestCaseResult.fetch_by_ids(submission_id,
                                                       test_case.id)
        if test_case.id not in results:
            if test_case_result:  # Delete existing result
                session.delete(test_case_result)
        else:
            if test_case_result:
                test_case_result.update(results[test_case.id])
            else:
                results[test_case.id]['submission_id'] = submission_id
                results[test_case.id]['test_case_id'] = test_case.id
                test_case_result = TestCaseResult(**results[test_case.id])
            if test_case.output_type == 'diff':
                compute_diff(test_case, test_case_result)
            else:
                output_file = 'tc_{0}'.format(test_case.id)
                if os.path.isfile(output_file):  # Store the file as the diff
                    test_case_result.diff = File.fetch_or_create(
                        open(output_file).read(), BASE_FILE_PATH)
            session.add(test_case_result)
    try:
        transaction.commit()
    except:
        transaction.abort()
        raise


def compute_diff(test_case, test_case_result):
    expected_output = readlines(File.file_path(BASE_FILE_PATH,
                                               test_case.expected.sha1))
    actual_output = readlines('tc_{0}'.format(test_case.id))
    unit = Diff(expected_output, actual_output)
    test_case_result.diff = File.fetch_or_create(pickle.dumps(unit),
                                                 BASE_FILE_PATH)


def start_communicator(conf_prefix, work_func):
    global BASE_FILE_PATH, PRIVATE_KEY_FILE
    parser = amqp_worker.base_argument_parser()
    args, settings = amqp_worker.parse_base_args(parser, 'app:main')
    BASE_FILE_PATH = settings['file_directory']
    PRIVATE_KEY_FILE = settings['ssh_priv_key']

    engine = engine_from_config(settings, 'sqlalchemy.')
    configure_sql(engine)

    worker = amqp_worker.AMQPWorker(
        settings['queue_server'], settings['queue_{0}'.format(conf_prefix)],
        work_func, is_daemon=args.daemon,
        log_file=settings['{0}_log_file'.format(conf_prefix)],
        pid_file=settings['{0}_pid_file'.format(conf_prefix)])
    worker.start()


def sync_files():
    start_communicator('sync_files', sync_files_worker)


@complete_file
def sync_files_worker(submission_id, testable_id, user, host, remote_dir):
    submission = Submission.fetch_by_id(submission_id)
    if not submission:
        raise Exception('Invalid submission id: {0}'.format(submission_id))
    testable = Testable.fetch_by_id(testable_id)
    if not testable:
        raise Exception('Invalid testable id: {0}'.format(testable_id))
    project = submission.project
    submitted = dict((x.filename, x.file.sha1) for x in submission.files)
    build_files = dict((x.filename, x.file.sha1) for x in testable.build_files)

    # Prepare build directory by symlinking the relevant submission files
    os.mkdir('src')
    for filev in testable.file_verifiers:
        if filev.filename in submitted:
            source = File.file_path(BASE_FILE_PATH, submitted[filev.filename])
            os.symlink(source, os.path.join('src', filev.filename))
            if filev.filename in build_files:
                del build_files[filev.filename]
        elif not filev.optional:
            raise Exception('File verifier not satisfied: {0}'
                            .format(filev.filename))
    for name, sha1 in build_files.items():  # Symlink remaining build files
        source = File.file_path(BASE_FILE_PATH, sha1)
        os.symlink(source, os.path.join('src', name))

    # Symlink Makefile to current directory if necessary
    if project.makefile and testable.make_target:
        source = File.file_path(BASE_FILE_PATH, project.makefile.sha1)
        os.symlink(source, 'Makefile')

    # Symlink test inputs and copy build test case specifications
    os.mkdir('inputs')
    test_cases = []
    for test_case in testable.test_cases:
        test_cases.append(test_case.serialize())
        if test_case.stdin:
            destination = os.path.join('inputs', test_case.stdin.sha1)
            if not os.path.isfile(destination):
                source = File.file_path(BASE_FILE_PATH, test_case.stdin.sha1)
                os.symlink(source, destination)

    # Copy execution files
    os.mkdir('execution_files')
    for execution_file in testable.execution_files:
        destination = os.path.join('execution_files', execution_file.filename)
        source = File.file_path(BASE_FILE_PATH, execution_file.file.sha1)
        os.symlink(source, destination)

    # Generate data dictionary
    data = {'executable': testable.executable,
            'make_target': testable.make_target,
            'test_cases': test_cases}

    # Save data specification
    with open('post_sync_data', 'w') as fp:
        json.dump(data, fp)

    # Rsync files
    cmd = 'rsync -e \'ssh -i {0}\' -rLpv . {1}@{2}:{3}'.format(
        PRIVATE_KEY_FILE, user, host, remote_dir)
    subprocess.check_call(cmd, stdout=open(os.devnull, 'w'), shell=True)
