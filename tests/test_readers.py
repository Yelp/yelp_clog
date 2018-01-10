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
from __future__ import print_function
import datetime
import os.path
import shutil
import tempfile
import time

import mock
import pytest

from clog import config, readers, loggers
from testing.sandbox import scribed_sandbox
from testing.sandbox import wait_on_log_data
from testing.sandbox import find_open_port
from testing.util import get_log_path


@pytest.mark.acceptance_suite
class TestCLogAcceptance(object):

    @pytest.yield_fixture(autouse=True)
    def do_setup(self):
        # find an open port for scribe server to listen on
        self.scribe_port = find_open_port()

        # make directory for scribe to write logs to
        self.scribe_logdir = tempfile.mkdtemp()

        # to store status reports we get back from clog
        self.status_reports = []
        yield
        shutil.rmtree(self.scribe_logdir)

    def report_status_callback(self, is_error, msg):
        self.status_reports.append((is_error, msg))

    def create_logger(self):
        return loggers.ScribeLogger('127.0.0.1',
                                 self.scribe_port,
                                 retry_interval=1,
                                 report_status=self.report_status_callback)

    def timed_writes(self, logger, count, timeout):
        """Write data using the logger and raise an error if the writes do
        not complete within timeout.
        """
        t0 = time.time()
        for i in range(count):
            logger.log_line('timed_writes', 'some data')
        dt = time.time() - t0
        assert dt < timeout

    def test_write_and_reconnect(self):
        with scribed_sandbox(self.scribe_port, self.scribe_logdir):
            logger = self.create_logger()
            logger.log_line('foo', '1')
            logger.log_line('foo', '2')
            logger.log_line('foo', u'☃')
            wait_on_log_data(
                get_log_path(self.scribe_logdir, 'foo'),
                u'1\n2\n☃\n'.encode('UTF-8'),
            )

        # make sure we haven't logged any errors
        assert not any(is_error for (is_error, msg) in self.status_reports)

        # write some more data, make sure we ignore that scribe server is
        # down, don't block too long
        self.timed_writes(logger, 10000, 2.0)

        # make sure we didn't log too many error reports
        assert len(self.status_reports) < 10
        # make sure we did log at least one error
        assert any(is_error for (is_error, msg) in self.status_reports)

        with scribed_sandbox(self.scribe_port, self.scribe_logdir):
            logger.log_line('foo', '3')
            logger.log_line('foo', '4')
            wait_on_log_data(
                get_log_path(self.scribe_logdir, 'foo'),
                u'1\n2\n☃\n3\n4\n'.encode('UTF-8'),
            )

    def test_init_while_down(self):
        logger = self.create_logger()
        self.timed_writes(logger, 10000, 2.0)

        # make sure we didn't log too many error reports
        assert len(self.status_reports) < 10
        # make sure we did log at least one error
        assert any(is_error for (is_error, msg) in self.status_reports)

        with scribed_sandbox(self.scribe_port, self.scribe_logdir):
            logger.log_line('bar', 'A')
            logger.log_line('bar', 'B')
            wait_on_log_data(get_log_path(self.scribe_logdir, 'bar'), b'A\nB\n')


@pytest.mark.acceptance_suite
class TestCLogStreamReaderAcceptance(object):

    @pytest.yield_fixture(autouse=True)
    def setup_reader(self):
        self.directory = tempfile.mkdtemp()
        self.date = datetime.date(2009, 1, 1)
        self.stream = 'stream_name'

        # Make 3 chunks with 10 log lines each:
        os.mkdir(os.path.join(self.directory, self.stream))
        for i in range(3):
            file_format = '%s-%%Y-%%m-%%d_%05d' % (self.stream, i)
            path = os.path.join(self.directory,
                                self.stream,
                                self.date.strftime(file_format))
            chunk_file = open(path, 'w')
            for i in range(10):
                print("A log line", file=chunk_file)
            chunk_file.close()

        self.num_expected_lines = 3 * 10
        yield
        shutil.rmtree(self.directory, ignore_errors=True)

    def test(self):
        stream_reader = readers.CLogStreamReader(self.directory,
                                                 self.stream,
                                                 self.date)
        num_lines = 0
        for line in stream_reader:
            num_lines += 1
            assert line == "A log line\n"
        assert self.num_expected_lines == num_lines


class TestFindTailHost(object):

    TEST_HOST = 'fake-host'
    TEST_TAIL_HOST = 'foo.bar.fake-host.com'

    @pytest.yield_fixture
    def mock_get_settings(self):
        with mock.patch('clog.readers.get_settings') as get_settings:
            get_settings.return_value = {self.TEST_HOST: self.TEST_TAIL_HOST}
            yield

    @pytest.yield_fixture
    def mock_get_settings_failed(self):
        with mock.patch('clog.readers.get_settings') as get_settings:
            get_settings.side_effect = IOError('missing file!')
            yield

    def test(self, mock_get_settings):
        tail_host = readers.find_tail_host(host=self.TEST_HOST)

        assert tail_host == self.TEST_TAIL_HOST

    def test_with_file_missing(self, mock_get_settings_failed):
        with pytest.raises(Exception):
            readers.find_tail_host(host=self.TEST_HOST)

    def test_with_host_key_missing(self, mock_get_settings):
        OTHER_TEST_HOST = 'fake-host-2'
        tail_host = readers.find_tail_host(host=OTHER_TEST_HOST)

        assert tail_host == OTHER_TEST_HOST


class TestStreamTailer(object):

    @pytest.yield_fixture
    def mock_find_tail_host(self):
        with mock.patch(
            'clog.readers.find_tail_host',
            autospec=True,
            return_value='fake-tail-host',
        ):
            yield

    @pytest.mark.parametrize('scribe_tail_services', [None, []])
    def test_no_host_no_config(self, mock_find_tail_host, scribe_tail_services):
        config.configure_from_dict({
            'scribe_tail_services': scribe_tail_services,
            'default_scribe_tail_port': 3535,
        })

        tailer = readers.StreamTailer('fake-stream')

        assert tailer.host == 'fake-tail-host'
        assert tailer.port == 3535

    def test_no_host_with_config(self, mock_find_tail_host):
        config_data = {
            'scribe_tail_services': [{
                'host': 'scribekafkaservices-fake-host',
                'port': 1234,
            }],
        }
        config.configure_from_dict(config_data)
        tailer = readers.StreamTailer('fake-stream')

        assert tailer.host == 'scribekafkaservices-fake-host'
        assert tailer.port == 1234
