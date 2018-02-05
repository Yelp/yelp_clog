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
import shutil
import tempfile

import mock
import pytest
import simplejson as json
import six

from clog import loggers
from clog.loggers import LogLineIsTooLongError
from clog.loggers import MAX_MONK_LINE_SIZE_IN_BYTES
from clog.loggers import MAX_SCRIBE_LINE_SIZE_IN_BYTES
from clog.loggers import MonkLogger
from clog.loggers import ScribeLogger
from clog.loggers import WARNING_SCRIBE_LINE_SIZE_IN_BYTES
from clog.loggers import WHO_CLOG_LARGE_LINE_STREAM
from testing.sandbox import find_open_port
from testing.sandbox import scribed_sandbox
from testing.sandbox import wait_on_log_data
from testing.util import create_test_line
from testing.util import get_log_path


@pytest.mark.acceptance_suite
class TestCLogScribeLoggerLineSize(object):

    @pytest.yield_fixture(autouse=True)
    def setup_sandbox(self):
        self.scribe_logdir = tempfile.mkdtemp()
        self.stream = 'foo'
        self.scribe_port = find_open_port()
        self.log_path = get_log_path(self.scribe_logdir, self.stream)

        self.logger = ScribeLogger(
            'localhost',
            self.scribe_port,
            retry_interval=10,
            report_status = mock.Mock()
        )

        with scribed_sandbox(self.scribe_port, self.scribe_logdir):
            yield
        shutil.rmtree(self.scribe_logdir)

    def test_line_size_constants(self):
        assert MAX_SCRIBE_LINE_SIZE_IN_BYTES == 50 * 1024 * 1024
        assert WARNING_SCRIBE_LINE_SIZE_IN_BYTES == 5 * 1024 * 1024
        assert WHO_CLOG_LARGE_LINE_STREAM == 'tmp_who_clog_large_line'

    def test_log_line_no_size_limit(self):
        line = create_test_line()
        self.logger._log_line_no_size_limit(self.stream, line)
        wait_on_log_data(self.log_path, line + b'\n')
        assert not self.logger.report_status.called

    @mock.patch('clog.loggers.ScribeLogger._log_line_no_size_limit')
    def test_normal_line_size(self, mock_log_line_no_size_limit):
        line = create_test_line()
        assert len(line) <= WARNING_SCRIBE_LINE_SIZE_IN_BYTES
        self.logger.log_line(self.stream, line)
        assert not self.logger.report_status.called
        mock_log_line_no_size_limit.assert_called_once_with(self.stream, line)

    @mock.patch('clog.loggers.ScribeLogger._log_line_no_size_limit')
    def test_max_line_size(self, mock_log_line_no_size_limit):
        line = create_test_line(MAX_SCRIBE_LINE_SIZE_IN_BYTES)
        assert len(line) > MAX_SCRIBE_LINE_SIZE_IN_BYTES
        with pytest.raises(LogLineIsTooLongError):
            self.logger.log_line(self.stream, line)
        assert self.logger.report_status.called_with(
            True,
            'The log line is dropped (line size larger than %r bytes)'
            % MAX_SCRIBE_LINE_SIZE_IN_BYTES
        )
        assert not mock_log_line_no_size_limit.called

    def test_large_msg(self):
        # We advertise support of messages up to 50 megs, so let's test that
        # we actually are able to log a 50 meg message to a real scribe server
        test_str = '0' * MAX_SCRIBE_LINE_SIZE_IN_BYTES
        self.logger.log_line(self.stream, test_str)
        expected = test_str.encode('UTF-8')
        wait_on_log_data(self.log_path, expected + b'\n')

    @mock.patch('traceback.format_stack')
    @mock.patch('clog.loggers.ScribeLogger._log_line_no_size_limit')
    def test_warning_line_size(self, mock_log_line_no_size_limit, mock_traceback):
        line = create_test_line(WARNING_SCRIBE_LINE_SIZE_IN_BYTES)
        assert len(line) > WARNING_SCRIBE_LINE_SIZE_IN_BYTES
        assert len(line) <= MAX_SCRIBE_LINE_SIZE_IN_BYTES
        self.logger.log_line(self.stream, line)
        assert self.logger.report_status.called_with(
            False,
            'The log line size is larger than %r bytes (monitored in \'%s\')'
            % (WARNING_SCRIBE_LINE_SIZE_IN_BYTES, WHO_CLOG_LARGE_LINE_STREAM)
        )
        assert mock_log_line_no_size_limit.call_count == 2
        call_1 = mock.call(self.stream, line)
        origin_info = {}
        origin_info['stream'] = self.stream
        origin_info['line_size'] = len(line)
        origin_info['line_preview'] = line[:1000]
        origin_info['traceback'] = ''.join(mock_traceback)
        origin_info_line = json.dumps(origin_info).encode('UTF-8')
        call_2 = mock.call(WHO_CLOG_LARGE_LINE_STREAM, origin_info_line)
        mock_log_line_no_size_limit.assert_has_calls([call_1, call_2])


@pytest.mark.acceptance_suite
class TestCLogMonkLoggerLineSize(object):

    @pytest.yield_fixture(autouse=True)
    def setup(self):
        self.stream = 'foo'
        loggers.MonkProducer = mock.Mock()
        self.logger = MonkLogger('clog_test_client_id')
        self.logger.report_status = mock.Mock()

    @mock.patch('clog.loggers.MonkLogger._log_line_no_size_limit', autospec=True)
    def test_normal_line_size(self, mock_log_line_no_size_limit):
        line = create_test_line()
        self.logger.log_line(self.stream, line)
        assert not self.logger.report_status.called
        call_1 = mock.call(mock.ANY, self.stream, line)
        mock_log_line_no_size_limit.assert_has_calls([call_1])

    @mock.patch('traceback.format_stack', autospec=True)
    @mock.patch('clog.loggers.MonkLogger._log_line_no_size_limit', autospec=True)
    def test_max_line_size(self, mock_log_line_no_size_limit, mock_traceback):
        line = create_test_line(MAX_MONK_LINE_SIZE_IN_BYTES)
        self.logger.log_line(self.stream, line)
        assert self.logger.report_status.call_count == 1
        assert mock_log_line_no_size_limit.call_count == 1
        expected_message_report = {
            'stream': self.stream,
            'line_size': len(line),
            'line_preview': line[:1000].decode('UTF-8') if six.PY3 else line[:1000],
            'traceback': ''.join(mock_traceback()),
        }
        _, dest_stream, message_report_json = mock_log_line_no_size_limit.mock_calls[0][1]
        assert dest_stream == WHO_CLOG_LARGE_LINE_STREAM
        assert json.loads(message_report_json) == expected_message_report
