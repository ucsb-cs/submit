import ConfigParser
import transaction
from argparse import ArgumentParser, FileType
from pyramid_addons.helpers import load_settings
from nudibranch.models import Session, Submission, initialize_sql
from sqlalchemy import engine_from_config
from . import QueueProcessor


def do_work(submission_id):
    session = Session()
    submission = Submission.fetch_by_id(submission_id)
    if not submission:
        print('Invalid submission id: {0}'.format(submission_id))
        return
    # Verify and update submission
    if submission.verify():
        retval = {'submission_id': submission_id}
    else:
        retval = None
    session.add(submission)
    transaction.commit()
    return retval


def main():
    parser = ArgumentParser()
    parser.add_argument('-D', '--not-daemon', action='store_false',
                        dest='daemon')
    parser.add_argument('ini_file', type=FileType())
    args = parser.parse_args()

    try:
        settings = load_settings(args.ini_file.name)
    except ConfigParser.Error as error:
        parser.error('Error with ini_file {0}: {1}'.format(args.ini_file.name,
                                                           error))

    engine = engine_from_config(settings, 'sqlalchemy.')
    initialize_sql(engine)

    queue_processor = QueueProcessor(settings['queue_server'],
                                     settings['queue_verification'],
                                     do_work, daemon=args.daemon,
                                     next_queue=settings['queue_tell_worker'])
    queue_processor.start()
