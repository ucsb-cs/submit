import amqp_worker
import json
import os
import subprocess
import pickle
from .exceptions import HandledError, OutOfSync
from nudibranch import workers
from nudibranch.diff_unit import Diff
from nudibranch.models import (File, Session, Submission, TestCaseResult,
                               Testable, TestableResult, configure_sql)
from sqlalchemy import engine_from_config


def fetch_results():
    start_communicator('fetch_results', fetch_results_worker)


def set_expected_files(testable, results):
    # Update the expected output of each test case
    for test_case in testable.test_cases:
        if test_case.id not in results:
            raise Exception('Missing test case result in project update: {0}'
                            .format(test_case.id))
        if test_case.output_type == 'diff':
            output_file = 'tc_{0}'.format(test_case.id)
            test_case.expected = File.fetch_or_create(
                open(output_file).read(), workers.BASE_FILE_PATH)
    testable.is_locked = False
    if not any(x.is_locked for x in testable.project.testables):
        testable.project.status = u'notready'


def rsync(user, host, remote_dir, from_local=False):
    src = '{}@{}:{}'.format(user, host, remote_dir)
    dst = '.'
    if from_local:
        src, dst = dst, src
    cmd = 'rsync -e \'ssh -i {}\' --timeout=16 -rLpv {} {}'.format(
        workers.PRIVATE_KEY_FILE, src, dst)
    try:
        subprocess.check_call(cmd, stdout=open(os.devnull, 'w'), shell=True)
    except subprocess.CalledProcessError:
        raise HandledError('rsync failed')


@workers.transaction_wrapper
@workers.complete_file
def fetch_results_worker(submission_id, testable_id, user, host, remote_dir,
                         update_project=False):
    submission = Submission.fetch_by_id(submission_id)
    if not submission:
        raise HandledError('Invalid submission id: {0}'.format(submission_id))
    testable = Testable.fetch_by_id(testable_id)
    if not testable:
        raise HandledError('Invalid testable id: {0}'.format(testable_id))
    if update_project and submission.project.status != u'locked':
        raise HandledError('Rejecting update to unlocked project: {0}'
                           .format(submission.project.id))
    if update_project and not testable.is_locked:
        raise HandledError('Rejecting update to unlocked testable: {0}'
                           .format(testable_id))

    # Rsync to retrieve results
    rsync(user, host, os.path.join(remote_dir, 'results/'))

    # Verify the results are for the correct submission and testable. If they
    # are not raise an exception so we don't put the "complete" file.
    expected_ids = [int(submission_id), testable_id]
    actual_ids = [int(x) for x in open('sync_files').read().split('.')]
    if expected_ids != actual_ids:
        raise OutOfSync('Fetch reulsts: Expected {0} Received {1}'
                        .format(expected_ids, actual_ids))

    # Create dictionary of completed test_cases
    if os.path.isfile('test_cases'):
        results = dict((int(x[0]), x[1]) for x
                       in json.load(open('test_cases')).items())
    else:
        results = {}

    if update_project:
        set_expected_files(testable, results)
        return

    points = 0

    # Set or update relevant test case results
    for test_case in testable.test_cases:
        test_case_result = TestCaseResult.fetch_by_ids(submission_id,
                                                       test_case.id)
        if test_case.id not in results:
            if test_case_result:  # Delete existing result
                Session.delete(test_case_result)
        else:
            if test_case_result:
                test_case_result.update(results[test_case.id])
            else:
                results[test_case.id]['submission_id'] = submission_id
                results[test_case.id]['test_case_id'] = test_case.id
                test_case_result = TestCaseResult(**results[test_case.id])
                Session.add(test_case_result)
            output_file = 'tc_{0}'.format(test_case.id)
            if test_case.output_type == 'diff':
                if compute_diff(test_case, test_case_result, output_file) and \
                        test_case_result.status == 'success':
                    points += test_case.points
            else:
                if os.path.isfile(output_file):  # Store the file as the diff
                    test_case_result.diff = File.fetch_or_create(
                        open(output_file).read(), workers.BASE_FILE_PATH)

    # Create or update Testable
    testable_data = json.load(open('testable'))
    TestableResult.fetch_or_create(
        make_results=testable_data.get('make'), points=points,
        status=testable_data['status'], testable=testable,
        submission=submission)


def compute_diff(test_case, test_case_result, output_file):
    """Associate the diff (if exists) with the TestCaseResult.

    Return whether or not the outputs match.

    """
    expected_output = open(File.file_path(workers.BASE_FILE_PATH,
                                          test_case.expected.sha1)).read()
    if os.path.isfile(output_file):
        actual_output = open('tc_{0}'.format(test_case.id)).read()
    else:
        actual_output = ''
    unit = Diff(expected_output, actual_output)
    if not unit.outputs_match():
        test_case_result.diff = File.fetch_or_create(pickle.dumps(unit),
                                                     workers.BASE_FILE_PATH)
        return False
    return True


def start_communicator(conf_prefix, work_func):
    parser = amqp_worker.base_argument_parser()
    args, settings = amqp_worker.parse_base_args(parser, 'app:main')
    workers.BASE_FILE_PATH = settings['file_directory']
    workers.PRIVATE_KEY_FILE = settings['ssh_priv_key']

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


@workers.transaction_wrapper
@workers.complete_file
def sync_files_worker(submission_id, testable_id, user, host, remote_dir):
    # Rsync to pre-sync files
    rsync(user, host, remote_dir + '/')

    # Verify a clean working directory and that the worker wants files for the
    # submission and testable. If they are not raise an exception so we don't
    # put the "complete" file.
    expected_files = set(['sync_verification'])
    actual_files = set(os.listdir('.'))
    if expected_files != actual_files:
        msg = 'Unexpected files: {0}'.format(actual_files - expected_files)
        raise OutOfSync('Sync files: {0}.{1} {2}'.format(submission_id,
                                                         testable_id,
                                                         msg))
    expected_ids = [int(submission_id), testable_id]
    actual_ids = [int(x) for x in open('sync_verification').read().split('.')]
    if expected_ids != actual_ids:
        raise OutOfSync('Sync files: Expected {0} Received {1}'
                        .format(expected_ids, actual_ids))

    submission = Submission.fetch_by_id(submission_id)
    if not submission:
        raise HandledError('Invalid submission id: {0}'.format(submission_id))
    testable = Testable.fetch_by_id(testable_id)
    if not testable:
        raise HandledError('Invalid testable id: {0}'.format(testable_id))
    project = submission.project
    submitted = dict((x.filename, x.file.sha1) for x in submission.files)
    build_files = dict((x.filename, x.file.sha1) for x in testable.build_files)

    # Prepare build directory by symlinking the relevant submission files
    os.mkdir('src')
    for filev in testable.file_verifiers:
        if filev.filename in submitted:
            source = File.file_path(workers.BASE_FILE_PATH,
                                    submitted[filev.filename])
            os.symlink(source, os.path.join('src', filev.filename))
            if filev.filename in build_files:
                del build_files[filev.filename]
        elif not filev.optional:
            raise HandledError('File verifier not satisfied: {0}'
                               .format(filev.filename))
    for name, sha1 in build_files.items():  # Symlink remaining build files
        source = File.file_path(workers.BASE_FILE_PATH, sha1)
        os.symlink(source, os.path.join('src', name))

    # Symlink Makefile to current directory if necessary
    if project.makefile and testable.make_target:
        source = File.file_path(workers.BASE_FILE_PATH, project.makefile.sha1)
        os.symlink(source, 'Makefile')

    # Symlink test inputs and copy build test case specifications
    os.mkdir('inputs')
    test_cases = []
    for test_case in testable.test_cases:
        test_cases.append(test_case.serialize())
        if test_case.stdin:
            destination = os.path.join('inputs', test_case.stdin.sha1)
            if not os.path.isfile(destination):
                source = File.file_path(workers.BASE_FILE_PATH,
                                        test_case.stdin.sha1)
                os.symlink(source, destination)

    # Copy execution files
    os.mkdir('execution_files')
    for execution_file in testable.execution_files:
        destination = os.path.join('execution_files', execution_file.filename)
        source = File.file_path(workers.BASE_FILE_PATH,
                                execution_file.file.sha1)
        os.symlink(source, destination)
    # Symlink sumbitted files that should be in the execution environment
    for filev in testable.file_verifiers:
        if filev.copy_to_execution and filev.filename in submitted:
            destination = os.path.join('execution_files', filev.filename)
            source = File.file_path(workers.BASE_FILE_PATH,
                                    submitted[filev.filename])
            os.symlink(source, destination)

    # Generate data dictionary
    data = {'executable': testable.executable,
            'make_target': testable.make_target,
            'test_cases': test_cases}

    # Save data specification
    with open('post_sync_data', 'w') as fp:
        json.dump(data, fp)

    # Rsync files
    rsync(user, host, remote_dir, from_local=True)
