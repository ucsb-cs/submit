import amqp_worker
import json
import os
import pickle
import random
import subprocess
import time
from heapq import heappop, heappush
from sqlalchemy import engine_from_config
from .exceptions import HandledError, SSHConnectTimeout
from .. import workers
from ..diff_unit import Diff
from ..models import (File, Session, Submission, TestCaseResult, Testable,
                      TestableResult, configure_sql)


def set_expected_files(testable, results, base_file_path):
    # Update the expected output of each test case
    for test_case in testable.test_cases:
        if test_case.id not in results:
            raise Exception('Missing test case result in project update: {0}'
                            .format(test_case.id))
        if test_case.output_type == 'diff':
            output_file = 'tc_{0}'.format(test_case.id)
            test_case.expected = File.fetch_or_create(
                open(output_file).read(), base_file_path)
    testable.is_locked = False
    if not any(x.is_locked for x in testable.project.testables):
        testable.project.status = u'notready'


def compute_diff(test_case, test_case_result, output_file, base_file_path):
    """Associate the diff (if exists) with the TestCaseResult.

    Return whether or not the outputs match.

    """
    with open(File.file_path(base_file_path, test_case.expected.sha1)) as fp:
        expected_output = fp.read()
    actual_output = ''
    if os.path.isfile(output_file):
        with open('tc_{0}'.format(test_case.id)) as fp:
            actual_output = fp.read()
    unit = Diff(expected_output, actual_output)
    if not unit.outputs_match():
        test_case_result.diff = File.fetch_or_create(pickle.dumps(unit),
                                                     base_file_path)
        return False
    return True


class WorkerProxy():
    def __init__(self):
        parser = amqp_worker.base_argument_parser()
        parser.add_argument('worker_account', type=str)
        args, settings = amqp_worker.parse_base_args(parser, 'app:main')

        self.base_file_path = settings['file_directory']
        self.private_key_file = settings['ssh_priv_key']
        self.account = args.worker_account
        machines = settings['worker_machines']
        if isinstance(machines, basestring):
            machines = [machines]
        random.shuffle(machines)
        self.machines = [(5., x) for x in machines]
        engine = engine_from_config(settings, 'sqlalchemy.')
        configure_sql(engine)

        worker = amqp_worker.AMQPWorker(
            settings['queue_server'], settings['queue_tell_worker'],
            self.do_work, is_daemon=args.daemon,
            error_queue=settings.get('queue_tell_worker_error'),
            log_file=settings['worker_proxy_log_file'].format(self.account),
            pid_file=settings['worker_proxy_pid_file'].format(self.account),
            email_subject='WorkerProxy {} Exception'.format(self.account),
            email_from=settings['exc_mail_from'],
            email_to=settings['exc_mail_to'])

        worker.handle_command(args.command)

    @workers.wrapper
    def do_work(self, submission_id, testable_id, update_project=False):
        # Verify job
        submission = Submission.fetch_by_id(submission_id)
        if not submission:
            raise HandledError('Invalid submission id: {0}'
                               .format(submission_id))
        testable = Testable.fetch_by_id(testable_id)
        if not testable:
            raise HandledError('Invalid testable id: {0}'.format(testable_id))
        if update_project and submission.project.status != u'locked':
            raise HandledError('Rejecting update to unlocked project: {0}'
                               .format(submission.project.id))
        if update_project and not testable.is_locked:
            raise HandledError('Rejecting update to unlocked testable: {0}'
                               .format(testable_id))

        attempt = 0
        while attempt < 16:
            # Fetch the best machine
            priority, machine = heappop(self.machines)
            # Log the start of the job
            workers.log_msg('{}.{} begin ({})'
                            .format(submission_id, testable_id, machine))
            log_type = 'unhandled'
            try:
                # Kill any processes on the worker
                priority = self.kill_processes(machine)
                # Copy the files to the worker (and remove existing files)
                self.push_files(machine, submission, testable)
                # Run the remote worker
                self.ssh(machine, 'python worker.py')
                # Fetch and generate the results
                self.fetch_results(machine, submission, testable,
                                   update_project)
                log_type = 'success'
                return
            except SSHConnectTimeout:  # Retry with a different host
                attempt += 1
                log_type = 'timeout'
                priority += 10
            except Exception:  # Increase priority and rereaise the exception
                log_type = 'exception'
                priority += 5
                raise
            finally:
                # Add the machine back to the queue
                heappush(self.machines, (priority, machine))
                # Log the end of the job
                workers.log_msg('{}.{} {} ({})'.format(submission_id,
                                                       testable_id, log_type,
                                                       machine))
        raise Exception('{}.{} timed out 16 times.'
                        .format(submission_id, testable_id))

    def fetch_results(self, machine, submission, testable, update_project):
        # Rsync to retrieve results
        self.rsync(machine)
        os.chdir('results')

        # Create dictionary of completed test_cases
        if os.path.isfile('test_cases'):
            with open('test_cases') as fp:
                results = {int(x[0]): x[1] for x in json.load(fp).items()}
        else:
            results = {}

        if update_project:
            set_expected_files(testable, results, self.base_file_path)
            return

        points = 0

        # Set or update relevant test case results
        for test_case in testable.test_cases:
            test_case_result = TestCaseResult.fetch_by_ids(submission.id,
                                                           test_case.id)
            if test_case.id not in results:
                if test_case_result:  # Delete existing result
                    Session.delete(test_case_result)
            else:
                if test_case_result:
                    test_case_result.update(results[test_case.id])
                else:
                    results[test_case.id]['submission_id'] = submission.id
                    results[test_case.id]['test_case_id'] = test_case.id
                    test_case_result = TestCaseResult(**results[test_case.id])
                    Session.add(test_case_result)
                output_file = 'tc_{0}'.format(test_case.id)
                if test_case.output_type == 'diff':
                    matches = compute_diff(test_case, test_case_result,
                                           output_file, self.base_file_path)
                    if matches and test_case_result.status == 'success':
                        points += test_case.points
                else:
                    if os.path.isfile(output_file):  # Store file as the diff
                        test_case_result.diff = File.fetch_or_create(
                            open(output_file).read(), self.base_file_path)

        # Create or update Testable
        testable_data = json.load(open('testable'))
        TestableResult.fetch_or_create(
            make_results=testable_data.get('make'), points=points,
            status=testable_data['status'], testable=testable,
            submission=submission)

    def kill_processes(self, machine):
        expected = 'Connection to {} closed by remote host.'.format(machine)
        start = time.time()
        try:
            self.ssh(machine, 'killall -9 -u {}'.format(self.account),
                     timeout=1)
            raise Exception('killall did not work as expected')
        except subprocess.CalledProcessError as exc:
            if exc.returncode != 255 or exc.output.strip() != expected:
                raise Exception('killall status: {} ({})'
                                .format(exc.returncode, exc.output.strip()))
        return time.time() - start

    def push_files(self, machine, submission, testable):
        submitted = {x.filename: x.file.sha1 for x in submission.files}
        build_files = {x.filename: x.file.sha1 for x in testable.build_files}

        # Prepare build directory by symlinking the relevant submission files
        os.mkdir('src')
        for filev in testable.file_verifiers:
            if filev.filename in submitted:
                source = File.file_path(self.base_file_path,
                                        submitted[filev.filename])
                os.symlink(source, os.path.join('src', filev.filename))
                if filev.filename in build_files:
                    del build_files[filev.filename]
            elif not filev.optional:
                raise HandledError('File verifier not satisfied: {0}'
                                   .format(filev.filename))
        for name, sha1 in build_files.items():  # Symlink remaining build files
            source = File.file_path(self.base_file_path, sha1)
            os.symlink(source, os.path.join('src', name))

        # Symlink Makefile to current directory if necessary
        if submission.project.makefile and testable.make_target:
            source = File.file_path(self.base_file_path,
                                    submission.project.makefile.sha1)
            os.symlink(source, 'Makefile')

        # Symlink test inputs and copy build test case specifications
        os.mkdir('inputs')
        test_cases = []
        for test_case in testable.test_cases:
            test_cases.append(test_case.serialize())
            if test_case.stdin:
                destination = os.path.join('inputs', test_case.stdin.sha1)
                if not os.path.isfile(destination):
                    source = File.file_path(self.base_file_path,
                                            test_case.stdin.sha1)
                    os.symlink(source, destination)

        # Copy execution files
        os.mkdir('execution_files')
        for execution_file in testable.execution_files:
            destination = os.path.join('execution_files',
                                       execution_file.filename)
            source = File.file_path(self.base_file_path,
                                    execution_file.file.sha1)
            os.symlink(source, destination)
        # Symlink sumbitted files that should be in the execution environment
        for filev in testable.file_verifiers:
            if filev.copy_to_execution and filev.filename in submitted:
                destination = os.path.join('execution_files', filev.filename)
                source = File.file_path(self.base_file_path,
                                        submitted[filev.filename])
                os.symlink(source, destination)

        # Generate data dictionary
        data = {'executable': testable.executable,
                'key': '{}.{}'.format(submission.id, testable.id),
                'make_target': testable.make_target,
                'test_cases': test_cases}

        # Save data specification
        with open('data.json', 'w') as fp:
            json.dump(data, fp)

        # Rsync files
        self.rsync(machine, from_local=True)

    def rsync(self, machine, from_local=False):
        src = '{}@{}:working/'.format(self.account, machine)
        dst = '.'
        if from_local:
            src, dst = dst, src
        cmd = ('rsync -e \'ssh -i {}\' --timeout=16 --delete -rLpv {} {}'
               .format(self.private_key_file, src, dst))
        subprocess.check_call(cmd, stdout=open(os.devnull, 'w'), shell=True)

    def ssh(self, machine, command, timeout=None):
        options = '-o ConnectTimeout={}'.format(timeout) if timeout else ''
        cmd = 'ssh -i {key} {options} {user}@{host} {command}'.format(
            key=self.private_key_file, user=self.account, host=machine,
            command=command, options=options)
        proc = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            if stderr.strip().endswith('Connection timed out'):
                raise SSHConnectTimeout()
            output = stdout + '\n' + stderr if stdout else stderr
            raise subprocess.CalledProcessError(proc.returncode, cmd,
                                                output=output)


def main():
    WorkerProxy()
