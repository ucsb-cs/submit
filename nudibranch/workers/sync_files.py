import ConfigParser
import amqp_worker
import os
import transaction
from nudibranch.models import Session, Submission, initialize_sql
from sqlalchemy import engine_from_config

PRIVATE_KEY_FILE = None


def do_work(submission_id, complete_file, user, host, working_dir):
    complete_file = os.path.join(working_dir, complete_file)
    command = 'echo {0} | ssh -i {1} {2}@{3} tee {4}'.format(
        submission_id, PRIVATE_KEY_FILE, user, host, complete_file)
    os.system(command)


def main():
    global PRIVATE_KEY_FILE
    parser = amqp_worker.base_argument_parser()
    args, settings = amqp_worker.parse_base_args(parser, 'app:main')
    PRIVATE_KEY_FILE = settings['ssh_priv_key']

    engine = engine_from_config(settings, 'sqlalchemy.')
    initialize_sql(engine)

    worker = amqp_worker.AMQPWorker(
        settings['queue_server'], settings['queue_sync_files'], do_work,
        is_daemon=args.daemon)
    worker.start()
