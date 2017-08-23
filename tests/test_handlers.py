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
import logging
import mock
import pytest

from clog import handlers, loggers


class TestScribeHandler(object):

    @pytest.fixture(autouse=True)
    def setup_handler(self):
        args = 'localhost', 4545, 'test_stream'
        self.handler = handlers.ScribeHandler(*args)
        self.record = logging.LogRecord(
            'name', logging.WARN, 'path', 50, 'oops', None, None)

    def test_init(self):
        assert self.handler.stream == 'test_stream'
        assert self.handler.logger.__class__ == loggers.ScribeLogger
        assert self.handler.logger.retry_interval is not None

    def test_emit_exception(self):
        self.handler.logger.log_line = mock.Mock()
        self.handler.logger.log_line.side_effect = Exception("Ooops")
        with mock.patch('sys.stderr') as mock_stderr:
            self.handler.emit(self.record)
            assert mock.call('Exception: Ooops\n') in mock_stderr.write.call_args_list

    def test_emit(self):
        self.handler.logger.log_line = mock.Mock()
        self.handler.emit(self.record)
        self.handler.logger.log_line.assert_called_with('test_stream', 'oops')

    def test_emit_interrupt_exception(self):
        self.handler.logger.log_line = mock.Mock()
        self.handler.logger.log_line.side_effect = KeyboardInterrupt("Stop")
        with pytest.raises(KeyboardInterrupt):
            self.handler.emit(self.record)


class TestMonkHandler(object):

    @pytest.fixture(autouse=True)
    def setup_handler(self):
        args = 'test_client', 'test_stream', 'localhost', 4545
        self.record = logging.LogRecord(
            'name', logging.WARN, 'path', 50, 'oops', None, None)
        with mock.patch.object(handlers, 'MonkLogger') as self.logger:
            self.handler = handlers.MonkHandler(*args)

    def test_init(self):
        assert self.handler.stream == 'test_stream'
        assert self.handler.logger == self.logger.return_value

    def test_emit_exception(self):
        self.handler.logger.log_line = mock.Mock()
        self.handler.logger.log_line.side_effect = Exception("Ooops")
        with mock.patch('sys.stderr') as mock_stderr:
            self.handler.emit(self.record)
            assert mock.call('Exception: Ooops\n') in mock_stderr.write.call_args_list

    def test_emit(self):
        self.handler.logger.log_line = mock.Mock()
        self.handler.emit(self.record)
        self.handler.logger.log_line.assert_called_with('test_stream', 'oops')

    def test_emit_interrupt_exception(self):
        self.handler.logger.log_line = mock.Mock()
        self.handler.logger.log_line.side_effect = KeyboardInterrupt("Stop")
        with pytest.raises(KeyboardInterrupt):
            self.handler.emit(self.record)


class TestCLogHandler(object):

    @pytest.fixture(autouse=True)
    def setup_handler(self):
        self.stream = 'stream_name'
        self.record = mock.MagicMock()

        # For ease of checking calls, make string concatenation return the same
        # object
        self.record.exc_text.__add__.return_value = self.record.exc_text
        self.record.exc_text.__radd__.return_value = self.record.exc_text

    def test_handler_default_logger(self):
        with mock.patch('clog.handlers.global_state') as mock_global:
            handler = handlers.CLogHandler(self.stream)
            handler.emit(self.record)
            mock_global.log_line.assert_called_with(
                self.stream, self.record.exc_text)

    def test_handler_custom_logger(self):
        logger = mock.Mock()
        handler = handlers.CLogHandler(self.stream, logger)
        handler.emit(self.record)
        logger.log_line.assert_called_with(
            self.stream, self.record.exc_text)
