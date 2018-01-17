# -*- coding: utf-8 -*-
# Copyright 2015 Yelp Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Loggers which implement `log_line(stream, data)` which are used to send log
data to a stream.
"""

from __future__ import print_function
from __future__ import with_statement

import atexit
import gzip
import os
import os.path
import sys
import syslog
import socket
import threading
import time
import traceback

import simplejson as json
import six
import pkg_resources

import thriftpy

monk_dependency_installed = True
try:
    from monk.producers import MonkProducer
except ImportError:
    monk_dependency_installed = False
    pass

from clog import config
from clog.metrics_reporter import MetricsReporter
from clog.utils import scribify

import thriftpy.transport.socket
# TODO(SRV-1467) Do not use the cython implementations
from thriftpy.protocol import TBinaryProtocolFactory
from thriftpy.thrift import TClient
from thriftpy.transport import TFramedTransportFactory
from thriftpy.transport import TTransportException


def _load_thrift():
    """Load the Scribe Thrift specification.

    The Thrift files we have are borrowed from the facebook-scribe repository here:
    https://github.com/tomprimozic/scribe-python

    As Scribe is now abandoned (per https://github.com/facebookarchive/scribe),
    it's highly unlikely that the scribe format will ever change.
    """
    # In the event that pkg_resources has to extract the thrift files from e.g.
    # a zip file to some temporary place, this asks it to clean them up
    atexit.register(pkg_resources.cleanup_resources)

    # Call this and discard the return value, just to ensure that this file is
    # available on the filesystem; it's included by scribe.thrift
    pkg_resources.resource_filename('clog', 'fb303.thrift')

    path = os.path.abspath(
        pkg_resources.resource_filename('clog', 'scribe.thrift'),
    )
    include_dir = os.path.dirname(path)
    return thriftpy.load(
        path, module_name='scribe_thrift', include_dirs=[include_dir])


scribe_thrift = _load_thrift()


# INFRA-2514:
# We do not want to have large log lines in scribe and later in kafka.
# If a line size is larger than 50 MB, it will be dropped with an exception raised.
# If it is larger than 5 MB, the origin of the message will be logged.
MAX_SCRIBE_LINE_SIZE_IN_BYTES = 52428800  # 50 MB
WARNING_SCRIBE_LINE_SIZE_IN_BYTES = 5242880  # 5 MB
# Log lines logged to Monk will be dropped if larger than 5MB
MAX_MONK_LINE_SIZE_IN_BYTES = 5242880  # 5 MB
WHO_CLOG_LARGE_LINE_STREAM = 'tmp_who_clog_large_line'


def report_to_syslog(is_error, msg):
    # only report errors to syslog
    syslog.openlog(ident="clog")
    if is_error:
        syslog.syslog(syslog.LOG_ALERT | syslog.LOG_USER, msg)


def report_to_stderr(is_error, msg):
    print(msg, ('(ERROR)' if is_error else '(INFO)'), file=sys.stderr)


def get_default_reporter(use_syslog=None):
    """Returns the default reporter based on the value of the argument

    :param report_to_syslog: Whether to use syslog or stderr. Defaults to the value
        of `config.scribe_errors_to_syslog`
    """
    use_syslog = use_syslog if use_syslog is not None else config.scribe_errors_to_syslog
    return report_to_syslog if use_syslog else report_to_stderr


def create_oversize_message_report(stream, line, preview_size=1000, traceback_size=5000):
    message_report = {
        'stream': stream,
        'line_size': len(line),
        'line_preview': line[:preview_size],
        'traceback': ''.join(traceback.format_stack())[:traceback_size],
    }
    return json.dumps(message_report).encode('UTF-8')


class ScribeIsNotForkSafeError(Exception):
    pass


class LogLineIsTooLongError(Exception):
    pass


class ScribeLogger(object):
    """Implementation that logs to a scribe server. If errors are encountered,
    drop lines and retry occasionally.

    :param host: hostname of the scribe server
    :param port: port number of the scribe server
    :param retry_interval: number of seconds to wait between retries
    :param report_status: a function `report_status(is_error, msg)` which is
        called to print out errors and status messages. The first
        argument indicates whether what is being printed is an error or not,
        and the second argument is the actual message.
    :param logging_timeout: milliseconds to time out scribe logging; "0" means
        blocking (no timeout)
    """

    def __init__(self, host, port, retry_interval, report_status=None, logging_timeout=None, stream_backend_map={}):
        # set up thrift and scribe objects
        timeout = logging_timeout if logging_timeout is not None else config.scribe_logging_timeout
        self.socket = thriftpy.transport.socket.TSocket(six.text_type(host), int(port))
        if timeout:
            self.socket.set_timeout(timeout)

        self.stream_backend_map = stream_backend_map
        self.transport = TFramedTransportFactory().get_transport(self.socket)
        protocol = TBinaryProtocolFactory(strict_read=False).get_protocol(self.transport)
        self.client = TClient(scribe_thrift.scribe, protocol)

        # our own bookkeeping for connection
        self.connected = False # whether or not we think we're currently connected to the scribe server
        self.last_connect_time = 0 # last time we got disconnected or failed to reconnect

        self.retry_interval = retry_interval
        self.report_status = report_status or get_default_reporter()
        self.__lock = threading.RLock()
        self._birth_pid = os.getpid()

        self.metrics = MetricsReporter(
            sample_rate=config.metrics_sample_rate,
            backend="scribe"
        )

    def _maybe_reconnect(self):
        """Try (re)connecting to the server if it's been long enough since our
        last attempt.
        """
        assert self.connected == False

        # don't retry too often
        now = time.time()
        if (now - self.last_connect_time) > self.retry_interval:
            try:
                self.transport.open()
                self.connected = True
            except TTransportException:
                self.last_connect_time = now
                self.report_status(True, 'yelp_clog failed to connect to scribe server')

    def _log_line_no_size_limit(self, stream, line):
        """Log a single line without size limit. It should not include any newline characters.
           Since this method is called in log_line, the line should be in utf-8 format and
           less than MAX_SCRIBE_LINE_SIZE_IN_BYTES already.
        """
        with self.__lock, self.metrics.sampled_request():
            if os.getpid() != self._birth_pid:
                raise ScribeIsNotForkSafeError
            if not self.connected:
                self._maybe_reconnect()

            if self.connected:
                log_entry = scribe_thrift.LogEntry(category=scribify(stream), message=line + b'\n')
                try:
                    return self.client.Log(messages=[log_entry])
                except Exception as e:
                    try:
                        self.report_status(
                            True,
                            'yelp_clog failed to log to scribe server with '
                            ' exception: %s(%s)' % (type(e), six.text_type(e))
                        )
                    finally:
                        self.close()
                        self.last_connect_time = time.time()

                    # Don't reconnect if report_status raises an exception
                    self._maybe_reconnect()

    def log_line(self, stream, line):
        """Log a single line. It should not include any newline characters.
           If the line size is over 50 MB, an exception raises and the line will be dropped.
           If the line size is over 5 MB, a message consisting origin stream information
           will be recorded at WHO_CLOG_LARGE_LINE_STREAM (in json format).
        """
        backend = self.stream_backend_map.get(stream, config.default_backend)
        if backend not in ('scribe', 'dual'):
            return

        # log unicodes as their utf-8 encoded representation
        if isinstance(line, six.text_type):
            line = line.encode('UTF-8')

        # check log line size
        if len(line) <= WARNING_SCRIBE_LINE_SIZE_IN_BYTES:
            self._log_line_no_size_limit(stream, line)
        elif len(line) <= MAX_SCRIBE_LINE_SIZE_IN_BYTES:
            self._log_line_no_size_limit(stream, line)

            # log the origin of the stream with traceback to WHO_CLOG_LARGE_LINE_STREAM category
            oversize_message_report = create_oversize_message_report(stream, line)
            self._log_line_no_size_limit(WHO_CLOG_LARGE_LINE_STREAM, oversize_message_report)
            self.report_status(
                False,
                'The log line size is larger than %r bytes (monitored in \'%s\')'
                % (WARNING_SCRIBE_LINE_SIZE_IN_BYTES, WHO_CLOG_LARGE_LINE_STREAM)
            )
        else:
            # raise an exception if too large
            self.report_status(
                True,
                'The log line is dropped (line size larger than %r bytes)'
                % MAX_SCRIBE_LINE_SIZE_IN_BYTES
            )
            raise LogLineIsTooLongError('The max log line size allowed is %r bytes'
                % MAX_SCRIBE_LINE_SIZE_IN_BYTES)

    def close(self):
        self.transport.close()
        self.connected = False


class MonkLogger(object):
    """Wrapper around MonkProducer"""

    def __init__(self, client_id, host=None, port=None, stream_backend_map={}):
        self.stream_prefix = config.monk_stream_prefix
        self.report_status = get_default_reporter()
        self.metrics = MetricsReporter(
            sample_rate=config.metrics_sample_rate,
            backend="monk"
        )
        self.timeout_backoff_s = config.monk_timeout_backoff_ms / 1000
        self.stream_backend_map = stream_backend_map
        self.last_timeout = time.time() - self.timeout_backoff_s
        self.producer = MonkProducer(
            client_id,
            host,
            port,
            timeout_ms=config.monk_timeout_ms,
            collect_metrics=False
        )

    def log_line(self, stream, line):
        backend = self.stream_backend_map.get(stream, config.default_backend)
        if backend not in ('monk', 'dual'):
            return

        # For backward-compatibility with the ScribeLogger
        stream = scribify(stream)
        if len(line) <= MAX_MONK_LINE_SIZE_IN_BYTES:
            self._log_line_no_size_limit(stream, line)
        else:
            # log the origin of the stream with traceback to WHO_CLOG_LARGE_LINE_STREAM
            oversize_message_report = create_oversize_message_report(stream, line)
            self._log_line_no_size_limit(WHO_CLOG_LARGE_LINE_STREAM, oversize_message_report)
            self.report_status(
                False,
                'The log line size is larger than %r bytes (monitored in \'%s\')'
                % (MAX_MONK_LINE_SIZE_IN_BYTES, WHO_CLOG_LARGE_LINE_STREAM)
            )
            self.metrics.monk_exception()


    def _log_line_no_size_limit(self, stream, line):
        if time.time() < self.last_timeout + self.timeout_backoff_s:
            return
        with self.metrics.sampled_request():
            try:
                self.producer.send_messages(
                    self.stream_prefix + stream,
                    [line],
                    None
                )
            except socket.timeout as e:
                self.report_status(True, 'Monk took too long to respond')
                self.last_timeout = time.time()
                self.metrics.monk_timeout()
            except Exception as e:
                self.report_status(
                    True,
                    'Exception while sending to monk: %s' % str(e)
                )
                self.metrics.monk_exception()

    def close(self):
        self.producer.close()


class FileLogger(object):
    """Implementation that logs to local files under a directory"""

    def __init__(self):
        self.stream_files = {}

    def log_line(self, stream, line):
        # N.B. we don't scribify() the stream name here, so if you have unusual
        # characters in the stream name the local file name could be different
        # from the scribe name.
        if stream not in self.stream_files:
            try:
                # open file in log directory with name STREAM.log, in unbuffered mode
                self.stream_files[stream] = self._create_file(stream)
            except IOError:
                print(
                    "Unable to open file for stream {stream} in directory {directory}".format(
                        stream=stream,
                        directory=config.log_dir,
                    ),
                    file=sys.stderr,
                )
                raise

        if isinstance(line, six.text_type):
            line = line.encode('UTF-8')
        self.stream_files[stream].write(line + b'\n')

    def close(self):
        for name in self.stream_files:
            self.stream_files[name].close()

    def _create_file(self, stream):
        return open(os.path.join(config.log_dir, stream + '.log'), 'ab', 0)


class GZipFileLogger(FileLogger):
    """Implementation of a logger that logs to local gzipped files."""

    dated_name_template = '%%s-%Y-%m-%d.log.gz'
    name_template = '%s.log.gz'

    def __init__(self, day=None):
        """If day is specified, log to a file named <stream>-yyyy-mm-dd.log.gz"""
        super(GZipFileLogger, self).__init__()
        self.day = day

    def _create_file(self, stream):
        name = self.get_filename(stream, self.day)
        return gzip.open(name, 'a')

    @classmethod
    def get_filename(cls, stream, day=None):
        if day:
            name = day.strftime(cls.dated_name_template) % stream
        else:
            name = cls.name_template % stream
        return os.path.join(config.log_dir, name)


class MockLogger(object):
    """Mock implementation for testing"""

    def __init__(self):
        self.lines = {}

    def log_line(self, stream, line):
        assert isinstance(stream, (bytes, six.text_type)), type(stream)
        assert isinstance(line, (bytes, six.text_type)), type(line)
        self.lines.setdefault(stream, []).append(line)

    def clear_lines(self, stream):
        del self.lines.setdefault(stream, [])[:]

    def list_lines(self, stream):
        return self.lines.setdefault(stream, [])

    def close(self):
        pass


class StdoutLogger(object):
    """Implementation that logs to stdout with stream name as a prefix."""

    def log_line(self, stream, line):
        sys.stdout.write('{0}:{1}\n'.format(stream, line))

    def close(self):
        sys.stdout.flush()
