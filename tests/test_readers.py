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

# -*- coding: utf-8 -*-
from __future__ import print_function
from builtins import range
import datetime
import os.path
import shutil
import tempfile
import time

import pytest
from testifycompat import setup, teardown, assert_equal
from testifycompat import assert_lt

from clog import readers, loggers
from testing.sandbox import scribed_sandbox
from testing.sandbox import wait_on_log_data
from testing.sandbox import find_open_port
from testing.util import get_log_path


@pytest.mark.acceptance_suite
class TestCLogAcceptance(object):

    @setup
    def do_setup(self):
        # find an open port for scribe server to listen on
        self.scribe_port = find_open_port()

        # make directory for scribe to write logs to
        self.scribe_logdir = tempfile.mkdtemp()

        # to store status reports we get back from clog
        self.status_reports = []

    @teardown
    def cleanup_logs(self):
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
        assert_lt(dt, timeout)

    def test_write_and_reconnect(self):
        with scribed_sandbox(self.scribe_port, self.scribe_logdir):
            logger = self.create_logger()
            logger.log_line('foo', '1')
            logger.log_line('foo', '2')
            wait_on_log_data(get_log_path(self.scribe_logdir, 'foo'), b'1\n2\n')

        # make sure we haven't logged any errors
        assert not any(is_error for (is_error, msg) in self.status_reports)

        # write some more data, make sure we ignore that scribe server is
        # down, don't block too long
        self.timed_writes(logger, 10000, 2.0)

        # make sure we didn't log too many error reports
        assert_lt(len(self.status_reports), 10)
        # make sure we did log at least one error
        assert any(is_error for (is_error, msg) in self.status_reports)

        with scribed_sandbox(self.scribe_port, self.scribe_logdir):
            logger.log_line('foo', '3')
            logger.log_line('foo', '4')
            wait_on_log_data(get_log_path(self.scribe_logdir, 'foo'), b'1\n2\n3\n4\n')

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

    @setup
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

    @teardown
    def cleanup_logs(self):
        shutil.rmtree(self.directory, ignore_errors=True)

    def test(self):
        stream_reader = readers.CLogStreamReader(self.directory,
                                                 self.stream,
                                                 self.date)
        num_lines = 0
        for line in stream_reader:
            num_lines += 1
            assert_equal(line, "A log line\n")
        assert_equal(self.num_expected_lines, num_lines)
