import amqp_worker
from sqlalchemy import engine_from_config
from .. import workers
from ..models import Submission, configure_sql

# Hack for old pickle files
# TODO: Migrate this data to not use pickle
import submit
import sys
sys.modules['nudibranch'] = submit
sys.modules['nudibranch.diff_unit'] = submit.diff_unit
sys.modules['nudibranch.models'] = submit.models


@workers.wrapper
def do_work(submission_id, update_project=False):
    submission = Submission.fetch_by_id(submission_id)
    if not submission:
        workers.log_msg('Invalid submission id: {0}'.format(submission_id))
        return
    if update_project and not submission.project.status == u'locked':
        workers.log_msg('Project to update is not locked: {0}'
                        .format(submission_id))
        return
    # Verify and update submission
    valid_testables = submission.verify(workers.BASE_FILE_PATH,
                                        update=not update_project)

    # All testables must be valid in order to update the project
    if update_project:
        for testable in submission.project.testables:
            if testable not in valid_testables:
                workers.log_msg(
                    'Cannot update project due to invalid testable: {}'
                    .format(testable.id))
            elif not testable.is_locked:
                workers.log_msg(
                    'Cannot update project due to unlocked testable: {}'
                    .format(testable.id))
            else:
                continue
            valid_testables = None
            break
    if valid_testables:
        workers.log_msg('Passed: {0}'.format(submission_id))
        retval = [{'submission_id': submission_id, 'testable_id': x.id,
                   'update_project': update_project}
                  for x in valid_testables]
    else:
        workers.log_msg('Failed: {0}'.format(submission_id))
        if update_project:
            submission.project.status = u'notready'
            for testable in submission.project.testables:
                testable.is_locked = False
        retval = None
    return retval


def main():
    parser = amqp_worker.base_argument_parser()
    args, settings = amqp_worker.parse_base_args(parser, 'app:main')
    workers.BASE_FILE_PATH = settings['file_directory']

    engine = engine_from_config(settings, 'sqlalchemy.')
    configure_sql(engine)

    worker = amqp_worker.AMQPWorker(
        settings['queue_server'], settings['queue_verification'], do_work,
        is_daemon=args.daemon, complete_queue=settings['queue_tell_worker'],
        error_queue=settings.get('queue_verification_error'),
        log_file=settings['verification_log_file'],
        pid_file=settings['verification_pid_file'],
        email_subject='Verification Exception',
        email_from=settings['exc_mail_from'], email_to=settings['exc_mail_to'])

    worker.handle_command(args.command)
