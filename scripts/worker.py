#!/usr/bin/env python
import ConfigParser
import amqp_worker
import json
import os
import pika
import pwd
import shutil
import socket
import sys
import time


class SubmissionHandler(object):
    @staticmethod
    def _cleanup():
        for filename in os.listdir('.'):
            if os.path.isdir(filename):
                shutil.rmtree(filename)
            else:
                os.unlink(filename)

    @staticmethod
    def _file_wait(filename, submission_id):
        start = time.time()
        while True:
            if os.path.isfile(filename):
                if open(filename).read() != str(submission_id):
                    raise Exception('Found wrong submission')
                print('file_wait took {0} seconds'.format(time.time() - start))
                return
            time.sleep(1)

    def __init__(self, settings, is_daemon):
        settings['working_dir'] = os.path.expanduser(settings['working_dir'])
        self.worker = amqp_worker.AMQPWorker(
            settings['server'], settings['queue_tell_worker'], self.do_work,
            is_daemon=is_daemon, working_dir=settings['working_dir'])
        self.settings = settings

    def communicate(self, queue, complete_file, submission_id):
        hostname = socket.gethostbyaddr(socket.gethostname())[0]
        username = pwd.getpwuid(os.getuid())[0]
        data = {'complete_file': complete_file, 'remote_dir': os.getcwd(),
                'user': username, 'host': hostname,
                'submission_id': submission_id}
        self.worker.channel.queue_declare(queue=queue, durable=True)
        self.worker.channel.basic_publish(
            exchange='', body=json.dumps(data), routing_key=queue,
            properties=pika.BasicProperties(delivery_mode=2))
        self._file_wait(complete_file, submission_id)

    def do_work(self, submission_id):
        self._cleanup()
        print('Got job: {0}'.format(submission_id))
        self.communicate(queue=self.settings['queue_sync_files'],
                         complete_file='sync_files',
                         submission_id=submission_id)
        print('Files synced: {0}'.format(submission_id))
        print(os.listdir('.'))
        # Make submission
        # Run tests
        self.communicate(queue=self.settings['queue_fetch_results'],
                         complete_file='results_fetched',
                         submission_id=submission_id)
        print('Results fetched: {0}'.format(submission_id))


def main():
    parser = amqp_worker.base_argument_parser()
    args, settings = amqp_worker.parse_base_args(parser, 'worker')
    handler = SubmissionHandler(settings, args.daemon)
    handler.worker.start()


if __name__ == '__main__':
    sys.exit(main())
