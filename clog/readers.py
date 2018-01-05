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
Classes which read log data from scribe.
"""
from __future__ import print_function

from clog.scribe_net import ScribeS3, ScribeReader

from io import BytesIO
import errno
import logging
import os
import os.path
import random
import re
import socket
import sys
import time
import traceback
import signal
import yaml
from datetime import timedelta
from simplejson import load
from staticconf.errors import ConfigurationError
from tempfile import TemporaryFile

from clog import config
from clog.utils import open_compressed_file

_chunkfile_pat = re.compile(r'^(?P<stream>[a-z][-a-z0-9_]+)-(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})(-(?P<source>[^_]*))?_(?P<chunk>\d+)([.]gz)?$')

COMPRESSED_HEADER_FMT = "<Q"

SETTINGS_FILE = '/nail/srv/configs/yelp_clog.json'


class NoLogDataError(Exception):
    pass


class CLogStreamReader(object):
    """Make a stream reader for a day of :mod:`clog` entries

    :mod:`clog` entries are stored by stream name and date and broken into
    separate chunks which may or may not be compressed with gzip or bzip or be
    plaintext.

    For instance, the entries for a stream called 'foo' on New Years Day 2009
    will be laid out in the file system like

    | STREAM_DIR/foo/foo-2009-01-01_00000.gz
    | STREAM_DIR/foo/foo-2009-01-01_00001.gz
    | ...

    Example usage:

    .. code-block:: python

        reader = CLogStreamReader('stream_name', '/path/to/logs', date.today())
        for line in reader:
            print line

    :param stream_dir: the stream directory like `/storage/coraid5/scribe_logs`
    :param stream_name: the stream name like `biz_views`
    :param date: the date of the logs
    :param fail_on_missing: Fail if there are no log files for the specified
        stream and date
    """

    def __init__(self, stream_name, stream_dir, date, fail_on_missing=False):
        self.stream_dir = stream_dir
        self.stream_name = stream_name
        self.date = date
        self.fail_on_missing = fail_on_missing

    def __repr__(self):
        return '%s(%r, %r, %r)' % (self.__class__.__name__, self.stream_name, self.stream_dir, self.date)

    def chunk_filenames(self):
        """Get an iterator for all the chunk filenames"""
        if not self.stream_name:
            return []
        stream_path = os.path.join(self.stream_dir, self.stream_name)

        result = []
        for root, _dirnames, filenames in os.walk(stream_path):
            for filename in filenames:
                chunk_match = _chunkfile_pat.match(filename)
                if chunk_match:
                    year = int(chunk_match.groupdict()['year'])
                    month = int(chunk_match.groupdict()['month'])
                    day = int(chunk_match.groupdict()['day'])
                    if (year, month, day) == (self.date.year, self.date.month,
                            self.date.day):
                        result.append(os.path.join(root, filename))

        if not result and self.fail_on_missing:
            raise NoLogDataError((stream_path, self.date))

        return sorted(result)

    def __iter__(self):
        return iter(CLogStreamIterator(self))


class CLogStreamIterator(object):
    """Iterator used by :class:`ClogStreamReader` for  iterating over lines
    of chunks of a stream.
    """
    log = logging.getLogger('yelp_lib.clog.CLogStreamIterator')

    def __init__(self, stream_reader, line_num=-1, current_chunk=None, chunk_line_num=-1):
        self.stream_reader = stream_reader
        self.line_num = line_num
        self.chunk_line_num = chunk_line_num
        self.current_chunk = current_chunk

    def __iter__(self):
        """Iterate over all the lines for all of the chunk files for this
        reader's stream and date.

        Yields
        byte string, A line in a chunk file;  e.g. an Apache access log line
        """
        self.line_num = 0
        for chunk_filename in self.stream_reader.chunk_filenames():
            self.log.debug('opening chunk: %s', (chunk_filename, ))

            try:
                self.current_chunk = open_compressed_file(chunk_filename, mode='r')
            except IOError as e:
                if e.errno == errno.ENOENT:
                    # maybe the file was compressed during iteration (see #9735)
                    for ext in ('.gz', '.bz2'):
                        compressed_name = chunk_filename + ext
                        if os.path.exists(compressed_name):
                            self.current_chunk = open_compressed_file(compressed_name, mode='r')
                            break
                    else:
                        raise
                else:
                    raise

            for line in self.current_chunk:
                self.line_num += 1
                self.chunk_line_num += 1
                yield line
            self.current_chunk.close()
            self.current_chunk = None
            self.chunk_line_num = -1


class StreamTailerSetupError(Exception):

    def __init__(self, host, port, message):
        super(StreamTailerSetupError, self).__init__()
        self.host = host
        self.port = port
        self.message = message

    def __str__(self):
        return "StreamTailerSetupError %s:%s -- %s" % (self.host, self.port, self.message)

    def __repr__(self):
        return "<StreamTailerSetupError host=%r port=%r message=%r>" % (self.host, self.port, self.message)

def get_settings(setting):
    with open(SETTINGS_FILE) as settings_file:
        settings = load(settings_file)
    return settings[setting]


def find_tail_host(host=None):
    try:
        if not host:
            host = get_settings('DEFAULT_SCRIBE_TAIL_HOST')
        tail_host = get_settings('HOST_TO_TAIL_HOST')[host]
        if tail_host == 'local':
            ecosystem = get_ecosystem_from_file()
            if ecosystem == 'prod':
                region = get_region_from_file()
                tail_host = get_settings('REGION_TO_TAIL_HOST')[region]
            else:
                tail_host = get_settings('ECOSYSTEM_TO_TAIL_HOST')[ecosystem]
    except KeyError:
        tail_host = host
    except IOError:
        raise
    return tail_host


class StreamTailer(object):
    """Tail a Scribe stream from a tailing server

    Example Usage:

    .. code-block:: python

        tailer = StreamTailer('stream_name', host, port)
        for line in tailer:
            print line

    Configuration:

    This class can be configured by passing a host and port to the constructor
    or by using :mod:`staticconf` with the following setting:

    **scribe_tail_services**
        (list of dicts {'host': host, 'port': port})
        list of host and port addresses of scribe endpoints for tailing logs
        in real time.

    :param stream: the name of the string like 'ranger'
    :type  stream: string
    :param host: the host name
    :type  host: string
    :param port: the port to connect to
    :type  port:
    :param bufsize: the number of bytes to buffer
    :param automagic_recovery: continue to retry connection forever
    :type  automagic_recovery: bool
    :param add_newline: add newlines to the items yielded in the iter
    :type  add_newlines: bool
    :param raise_on_start: raise an error if you get a disconnect immediately
                           after starting (otherwise, returns silently),
                           Default True
    :type  raise_on_start: bool
    :param timeout: connection timeout
    :type  timeout: int
    :param reconnect_callback: callback called when reconnecting
    :type  reconnect_callback: function
    :param protocol_opts: optional protocol parameters
    :type  protocol_opts: dict
    """

    scribe_tail_services = config.clog_namespace.get_list(
        'scribe_tail_services',
        default=None,
        help="List of Scribe endpoints for tailing, "
             "in the form {'host': host, 'port': port}")

    def __init__(self,
                 stream,
                 host=None,
                 port=None,
                 bufsize=4096,
                 automagic_recovery=True,
                 add_newlines=True,
                 raise_on_start=True,
                 timeout=None,
                 reconnect_callback=None,
                 use_kafka=config.use_kafka,
                 lines=None,
                 protocol_opts=None):
        if host is None or port is None:
            try:
                primary_tail_host = random.choice(self.scribe_tail_services)
                host = primary_tail_host['host']
                port = primary_tail_host['port']
            except (IndexError, ConfigurationError):
                host = find_tail_host()
                port = config.default_scribe_tail_port.value

        if use_kafka and not host.startswith('scribekafkaservices-'):
            self.host = find_tail_host(host)
        else:
            self.host = host

        self.port = port
        self.bufsize = bufsize
        self._stream = stream
        self._automagic_recovery = automagic_recovery
        self._add_newlines = add_newlines
        self._raise_on_start = raise_on_start
        self.timeout = timeout
        self._fd = None
        self._running = True
        self._reconnect_callback = reconnect_callback
        self._lines = lines
        self._protocol_opts = protocol_opts
        if self._lines:
            if not use_kafka:
                raise Exception("Last n lines can be only used with new kafka tailer")
            self._automagic_recovery = False
        signal.signal(signal.SIGTERM, self.handle_sigterm)

    def handle_sigterm(self, signum, frame):
        self._running = False
        self.close()

    def connect(self):
        for socket_info in socket.getaddrinfo(self.host,
                                              self.port,
                                              0,
                                              socket.SOCK_STREAM,
                                              0):

            family, socktype, proto, _canonname, sockaddr = socket_info
            try:
                fd = socket.socket(family, socktype, proto)
                fd.settimeout(self.timeout)
                fd.connect(sockaddr)
                self._fd = fd
                break
            except socket.error:
                pass
        if not self._fd:
            raise StreamTailerSetupError(
                    self.host,
                    self.port,
                    'Failed to connect (stream %r)' % (self._stream,))
        bytes_sent = 0
        msg = construct_conn_msg(self._stream, self._lines, self._protocol_opts).encode('utf8')
        while bytes_sent < len(msg):
            bytes_sent += self._fd.send(msg[bytes_sent:])

    def _recv_plaintext(self):
        return self._fd.recv(self.bufsize)

    def _recv_bytes(self, sock, size):
        """Read and return the next 'size' bytes from 'sock'."""
        buf = BytesIO()
        bytes_read = 0

        while bytes_read < size:
            data = sock.recv(size - bytes_read)
            if not data:
                return
            buf.write(data)
            bytes_read += len(data)

        return buf.getvalue()

    def _sockiter(self):
        at_start = True
        buffered = []
        newline_char = b'\n' if self._add_newlines else b''
        def reconnect():
            self._call_reconnect_callback()
            while not self._fd:
                try:
                    print("socket error, reconnecting", file=sys.stderr)
                    self.connect()
                except socket.error:
                    time.sleep(2)

        while self._running:
            try:
                dat = self._recv_plaintext()

                if not dat:
                    self._fd.close()
                    self._fd = None
                    if at_start:
                        if self._raise_on_start:
                            raise StreamTailerSetupError(
                                    self.host,
                                    self.port,
                                    'No data in stream %r' % (self._stream,))
                        else:
                            return
                    elif self._automagic_recovery and self._running:
                        reconnect()
                    else:
                        return
                at_start = False
                lines = dat.split(b'\n')
                if len(lines) > 1:
                    yield b''.join(buffered) + lines[0] + newline_char
                    for l in lines[1:-1]:
                        yield l + newline_char
                    buffered = lines[-1:]
                else:
                    buffered += lines
            except socket.error:
                if self._automagic_recovery:
                    reconnect()
                else:
                    raise

    def __iter__(self):
        if not self._fd:
            self.connect()
        return self._sockiter()

    def close(self):
        if self._fd:
            self._fd.close()

    def _call_reconnect_callback(self):
        try:
            if self._reconnect_callback is not None:
                self._reconnect_callback()
        except:
            traceback.print_exc()

    def list_streams(self):
        """Get a context manager to use for reading list names"""
        towrite = ""
        return NetCLogStreamReader._ContextManager(
            self,
            towrite,
            protocol_opts=self._protocol_opts,
        )

def construct_conn_msg(stream, lines=None, protocol_opts=None):
    """Return a connnection message

    :param stream: stream name
    :param lines: number of messages to consume
    :param protocol_opts: optional arguments
    """
    connection_msg = stream
    if lines:
        connection_msg += ' {0}'.format(lines)
    if protocol_opts:
        connection_msg += ''.join([' {0}={1}'.format(k, v) for k, v in protocol_opts.items()])
    return connection_msg + '\n'

def read_s3_keypair():
    with open("/etc/boto_cfg/scribereader.yaml") as f:
        aws_creds = yaml.load(f.read())
        return aws_creds['aws_access_key_id'], aws_creds['aws_secret_access_key']

def get_s3_info(hostname, stream_name=None):
    """Returns (s3_host, s3_bucket(s), s3_prefix)

    If no stream name is provided (i.e. None), both normal and tmp buckets are
    returned as a dict.
    """
    ecosystem = get_ecosystem(hostname)
    buckets = get_settings('ECOSYSTEM_TO_BUCKETS')[ecosystem]
    if stream_name:
        return get_settings('S3_HOST'), get_bucket(buckets, stream_name)
    return get_settings('S3_HOST'), buckets

def _split_bucket_and_prefix(bucket):
    bucket_prefix = bucket.split('/', 1)
    if len(bucket_prefix) == 1:
        return bucket_prefix[0], None
    else:
        return tuple(bucket_prefix)

def get_ecosystem(hostname):
    if hostname == 'scribe.local.yelpcorp.com':
        return get_ecosystem_from_file()
    else:
        return get_settings('HOST_TO_ECOSYSTEM')[hostname]

def get_ecosystem_from_file():
    with open("/nail/etc/ecosystem") as f:
        return f.read().strip()

def get_region_from_file():
    with open("/nail/etc/region") as f:
        return f.read().strip()

def get_bucket(buckets, stream_name):
    if stream_name.startswith('tmp_'):
        return buckets['tmp']
    else:
        return buckets['standard']

class NetCLogStreamReader(object):
    """Read logs from a scribe server

    .. note::

        This reader will stream logs from the source, it is not recommended
        for large logs.  Use a mrjob instead.

    Example usage:

    .. code-block:: python

        stream_reader = NetCLogStreamReader()
        with stream_reader.read_date_range(
                'ranger',
                date(2010, 1, 1),
                date(2010,12,31)
        ) as reader:
            for line in reader:
                print line


    Configuration:

    This class can be configured either by passing a `host` and `port` to
    the constructor, or by using :mod:`staticconf` to with the following
    settings

    **scribe_net_reader.host**
        hostname of the scribe server used to stream scribe logs

    **scribe_net_reader.port**
        port of the scribe server used to stream scribe logs


    :param bufsize: How many bytes to buffer internally
    :param host: The host to connect to (defaults to scribe_net_reader.host)
    :param port: The port to connect to (defaults to scribe_net_reader.port)
    :param automagic_recovery: Whether to tail the stream, continuously
        retrying the connection (defaults to False)
    """

    reader_host = config.clog_namespace.get_string('scribe_net_reader.host',
                                                   default=None)
    reader_port = config.clog_namespace.get_int('scribe_net_reader.port',
                                                default=None)

    def __init__(self, bufsize=1024, host=None, port=None, automagic_recovery=False, localS3=config.localS3):
        self.host = host or self.reader_host.value
        self.port = port or self.reader_port.value
        self.bufsize = int(bufsize)
        self.automagic_recovery = automagic_recovery
        self.localS3 = localS3

        self.aws_access_key_id, self.aws_secret_access_key = read_s3_keypair()

    class _ContextManager(object):
        """Root context manager. Does not issue any commands.

        All of these context managers strip the newlines when reading.
        """

        def __init__(self, stream_reader, message, protocol_opts=None):
            self.stream_reader = stream_reader
            self.message = message
            self.protocol_opts = protocol_opts

        def _connect(self):
            self._reader = StreamTailer(self.message,
                                        self.stream_reader.host,
                                        self.stream_reader.port,
                                        self.stream_reader.bufsize,
                                        automagic_recovery=False,
                                        add_newlines=False,
                                        raise_on_start=False,
                                        use_kafka=False,
                                        protocol_opts=self.protocol_opts)

        def __enter__(self):
            self._connect()
            return self._reader

        def __exit__(self, exc_type, exc_value, traceback):
            return self._reader.close()

    class DateRangeContextManager(object):
        def __init__(self, host, stream_name, start_date, end_date, aws_access_key_id, aws_secret_access_key):
            self.stream_name = stream_name
            self.start_date = start_date
            self.end_date = end_date
            s3_host, s3_bucket = get_s3_info(host, stream_name)
            bucket, prefix = _split_bucket_and_prefix(s3_bucket)
            self.s3_connection = ScribeS3(
                s3_host=s3_host,
                s3_bucket=bucket,
                s3_key_prefix=prefix,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
            )

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def __iter__(self):
            current_date = self.start_date
            while self.end_date >= current_date:
                with TemporaryFile() as temp_file:
                    self.reader = ScribeReader(
                        self.stream_name,
                        s3_connections=[self.s3_connection],
                        ostream=temp_file
                    )

                    for _ in self.reader.get_for_date(current_date):
                        temp_file.flush()
                        temp_file.seek(0)
                        for line in temp_file:
                            # Python 3 will return byte arrays instead of str
                            if isinstance(line, str):
                                yield line
                            else:
                                yield line.decode('utf-8')
                        temp_file.seek(0)
                        temp_file.truncate(0)

                    current_date += timedelta(1)

    def read_date_range(self, stream_name, start_date, end_date):
        """Get a context manager to use for reading a stream for a date range"""
        if self.localS3:
            return NetCLogStreamReader.DateRangeContextManager(
                self.host,
                stream_name,
                start_date,
                end_date,
                self.aws_access_key_id,
                self.aws_secret_access_key,
            )
        else:
            towrite = "get %s %04d-%02d-%02d %04d-%02d-%02d" % (stream_name,
                                                                start_date.year,
                                                                start_date.month,
                                                                start_date.day,
                                                                end_date.year,
                                                                end_date.month,
                                                                end_date.day)
            return NetCLogStreamReader._ContextManager(self, towrite)

    class ListContextManager(object):
        def __init__(self, host, aws_access_key_id, aws_secret_access_key):
            s3_host, s3_buckets = get_s3_info(host)
            s3_bucket, s3_prefix = _split_bucket_and_prefix(s3_buckets['standard'])
            s3_tmp_bucket, s3_tmp_prefix = _split_bucket_and_prefix(s3_buckets['tmp'])

            s3_connection = ScribeS3(
                s3_host=s3_host,
                s3_bucket=s3_bucket,
                s3_key_prefix=s3_prefix,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
            )
            streams = s3_connection.streams

            if s3_bucket != s3_tmp_bucket:
                s3_tmp_connection = ScribeS3(
                    s3_host=s3_host,
                    s3_bucket=s3_tmp_bucket,
                    s3_key_prefix=s3_tmp_prefix,
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                )
                tmp_streams = s3_tmp_connection.streams
            else:
                tmp_streams = []

            self.streams = streams.union(tmp_streams)

        def __enter__(self):
            return self.streams

        def __exit__(self, exc_type, exc_value, traceback):
            pass

    def list_streams(self):
        """Get a context manager to use for reading list names"""
        if self.localS3:
            return NetCLogStreamReader.ListContextManager(self.host, self.aws_access_key_id, self.aws_secret_access_key)
        else:
            towrite = "list"
            return NetCLogStreamReader._ContextManager(self, towrite)
