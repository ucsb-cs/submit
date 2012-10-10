import ConfigParser
import amqp_worker
import transaction
from nudibranch.models import Session, Submission, initialize_sql
from sqlalchemy import engine_from_config


def do_work(submission_id):
    session = Session()
    submission = Submission.fetch_by_id(submission_id)
    if not submission:
        print('Invalid submission id: {0}'.format(submission_id))
        return
    # Verify and update submission
    if submission.verify():
        print('Passed: {0}'.format(submission_id))
        retval = {'submission_id': submission_id}
    else:
        print('Failed: {0}'.format(submission_id))
        retval = None
    session.add(submission)
    transaction.commit()
    return retval


def main():
    parser = amqp_worker.base_argument_parser()
    args, settings = amqp_worker.parse_base_args(parser, 'app:main')

    engine = engine_from_config(settings, 'sqlalchemy.')
    initialize_sql(engine)

    worker = amqp_worker.AMQPWorker(
        settings['queue_server'], settings['queue_verification'], do_work,
        is_daemon=args.daemon, complete_queue=settings['queue_tell_worker'])
    worker.start()
