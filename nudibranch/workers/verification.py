import amqp_worker
import transaction
from nudibranch.models import Session, Submission, configure_sql
from sqlalchemy import engine_from_config

BASE_FILE_PATH = None


def do_work(submission_id):
    session = Session()
    submission = Submission.fetch_by_id(submission_id)
    if not submission:
        print('Invalid submission id: {0}'.format(submission_id))
        return
    # Verify and update submission
    valid_testables = submission.verify(BASE_FILE_PATH)
    if valid_testables:
        print('Passed: {0}'.format(submission_id))
        retval = [{'submission_id': submission_id, 'testable_id': x.id}
                  for x in valid_testables]
    else:
        print('Failed: {0}'.format(submission_id))
        retval = None
    session.add(submission)
    transaction.commit()
    return retval


def main():
    global BASE_FILE_PATH
    parser = amqp_worker.base_argument_parser()
    args, settings = amqp_worker.parse_base_args(parser, 'app:main')
    BASE_FILE_PATH = settings['file_directory']

    engine = engine_from_config(settings, 'sqlalchemy.')
    configure_sql(engine)

    worker = amqp_worker.AMQPWorker(
        settings['queue_server'], settings['queue_verification'], do_work,
        is_daemon=args.daemon, complete_queue=settings['queue_tell_worker'],
        log_file=settings['verification_log_file'],
        pid_file=settings['verification_pid_file'])
    worker.start()
