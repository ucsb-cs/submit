import daemon
import errno
import os
import pika
import socket
import sys
import time
import traceback


class QueueProcessor(object):
    MAX_SLEEP_TIME = 64

    def __init__(self, server, queue, worker_func, daemon=False, log_dir=None):
        self.server = server
        self.queue = queue
        self.worker_func = worker_func
        self.connection = None
        self.daemon = daemon
        self.log_dir = log_dir
        if not daemon and log_dir:
            raise Exception('daemon must be True when log_dir is set')

    def _start(self):
        sleep_time = 1
        iterations = 0
        running = True
        while running:
            try:
                if iterations > 0:
                    print('Retrying in {0} seconds'.format(sleep_time))
                    time.sleep(sleep_time)
                    sleep_time = min(self.MAX_SLEEP_TIME, sleep_time * 2)
                iterations += 1
                self.initialize_connection()
                sleep_time = 1
                self.receive_jobs()
            except socket.error as error:
                print('Error connecting to rabbitmq: {0!s}'.format(error))
            except pika.exceptions.AMQPConnectionError as error:
                print('Lost connection to rabbitmq')
            except Exception:
                traceback.print_exc()
            except KeyboardInterrupt:
                print('Goodbye!')
                running = False
            finally:
                # Force disconnect to release the jobs
                if self.connection:
                    if not self.connection.closed:
                        self.connection.close()
                    self.connection._adapter_disconnect()
                    self.connection = None

    def consume_callback(self, channel, method, properties, message):
        return_message = self.worker_func(message)
        if return_message:
            print(return_message)
        channel.basic_ack(delivery_tag=method.delivery_tag)

    def initialize_connection(self):
        print('Attempting connection')
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.server))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.queue, durable=True)
        self.channel.basic_qos(prefetch_count=1)
        print('Connected')

    def receive_jobs(self):
        self.channel.basic_consume(self.consume_callback, queue=self.queue)
        self.channel.start_consuming()

    def start(self):
        if self.daemon:
            log_filename = 'nb_worker_{0}'.format(self.queue)
            if self.log_dir:
                try:
                    os.makedirs(os.path.dirname(self.log_dir))
                except OSError as error:
                    if error.errno != errno.EEXIST:
                        raise
                log_filename = os.path.join(self.log_dir, log_filename)
            log_file = open(log_filename, 'a+')
            with daemon.DaemonContext(stdout=log_file, stderr=log_file):
                # Line-buffer the output streams
                sys.stdout = os.fdopen(sys.stdout.fileno(), 'a', 1)
                sys.stderr = os.fdopen(sys.stderr.fileno(), 'a', 1)
                self._start()
        else:
            self._start()
