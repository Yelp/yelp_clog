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
from __future__ import unicode_literals

from datetime import date, timedelta
import gzip
import logging
import os
import shutil
import tempfile

import mock
import pytest
import six
import staticconf.testing

from clog import loggers
from clog.handlers import CLogHandler, DEFAULT_FORMAT
from clog.handlers import get_scribed_logger
from clog.loggers import FileLogger, GZipFileLogger, MockLogger, MonkLogger, StdoutLogger
from clog.utils import scribify


first_line = 'First Line.'
second_line = 'Second Line.'
complete_line = '%s\n%s\n' % (first_line, second_line)


@pytest.yield_fixture
def log_directory():
    log_dir = tempfile.mkdtemp()
    with staticconf.testing.MockConfiguration(
        log_dir=log_dir, namespace='clog',
    ):
        yield log_dir
    shutil.rmtree(log_dir)


class TestGZipFileLogger(object):

    def _open_and_remove(self, filename):
        gz_fh = gzip.open(filename)
        content = gz_fh.read()
        gz_fh.close()
        os.remove(filename)
        return content.decode('utf8')

    def test_no_day(self, log_directory):
        logger = GZipFileLogger()
        stream = 'first'
        logger.log_line(stream, first_line)
        logger.log_line(stream, second_line)
        logger.close()

        log_filename = GZipFileLogger.get_filename(stream)
        content = self._open_and_remove(log_filename)
        assert content == complete_line

    def test_single_day(self, log_directory):
        stream = 'second'
        day = date.today()
        logger = GZipFileLogger(day=day)
        logger.log_line(stream, first_line)
        logger.log_line(stream, second_line)
        logger.close()

        log_filename = GZipFileLogger.get_filename(stream, day=day)
        content = self._open_and_remove(log_filename)
        assert content == complete_line

    def test_multi_day(self, log_directory):
        stream = 'multi'
        first_day = date.today()
        second_day = date.today() + timedelta(days=1)

        for day in (first_day, second_day):
            logger = GZipFileLogger(day=day)
            logger.log_line(stream, first_line)
            logger.log_line(stream, second_line)
            logger.close()

        for day in (first_day, second_day):
            log_filename = GZipFileLogger.get_filename(stream, day=day)
            content = self._open_and_remove(log_filename)
            assert content == complete_line


class TestFileLogger(object):

    def _open_and_remove(self, filename):
        with open(filename) as f:
            contents = f.read()

        os.remove(filename)
        if isinstance(contents, six.binary_type):
            return contents.decode('utf-8')
        else:
            return contents

    @pytest.mark.parametrize('line1, expected_output', [
        ('hello', 'hello\nworld\n'),
        ('☃', '☃\nworld\n'),
    ])
    def test_log_line(self, log_directory, line1, expected_output):
        logger = FileLogger()
        stream = 'file_logger_stream'
        logger.log_line(stream, line1)
        logger.log_line(stream, 'world')
        logger.close()

        assert self._open_and_remove(logger.stream_files[stream].name) == expected_output

    def test_cant_open_stream(self, log_directory, capsys):
        log_dir = os.path.join(log_directory, 'non_existent_directory')
        with staticconf.testing.MockConfiguration(log_dir=log_dir, namespace='clog'):
            logger = FileLogger()
            stream = 'first'
            with pytest.raises(IOError):
                logger.log_line(stream, first_line)

            stdout, stderr = capsys.readouterr()
            assert stderr == 'Unable to open file for stream first in directory {0}\n'.format(
                log_dir
            )


class MyError(Exception):
    pass


class CLogTestBase(object):
    SIMPLE_FORMAT="%(message)s"
    STREAM_NAME='unit_test'

    @pytest.fixture(autouse=True)
    def _create_logger(self):
        self.logger = MockLogger()
        self.handler = CLogHandler(stream=self.STREAM_NAME, logger=self.logger)
        self.handler.setFormatter(logging.Formatter(self.SIMPLE_FORMAT))
        self.log_instance = logging.getLogger(self.STREAM_NAME)
        self.log_instance.handlers = [self.handler]


class TestCLogHandler(CLogTestBase):

    def test_handler_preserves_exceptions(self):
        """Test exception preservation a la 18848"""
        # set the default formatter
        self.log_instance.handlers[0].setFormatter(logging.Formatter(DEFAULT_FORMAT))
        try:
            raise MyError("foobar")
        except MyError:
            self.log_instance.exception("example log message")
        assert 1 == len([message for message in self.logger.list_lines(self.STREAM_NAME) if "example log message" in message])


class TestMiscellaneousCLogMethods(CLogTestBase):
    def test_get_scribed_logger(self):
        log = get_scribed_logger("unit_test_scribed", logging.INFO, fmt=self.SIMPLE_FORMAT, clogger_object=self.logger)
        log.info("This is a test")
        assert "This is a test" in self.logger.list_lines("unit_test_scribed")
        self.logger.clear_lines("unit_test_scribed")
        # test that we don"t double-add
        log = get_scribed_logger("unit_test_scribed", logging.INFO, fmt=self.SIMPLE_FORMAT, clogger_object=self.logger)
        log.info("This is a test")
        assert 1 == len([message for message in self.logger.list_lines("unit_test_scribed") if message == "This is a test"])

    def test_scribify(self):
        # The rhs is intentionally native strings
        assert scribify(b'stream_service_errors') == str('stream_service_errors')
        assert scribify("this is a test") == str('this_is_a_test')
        assert scribify("this\0is a-test\n\n") == str('this_is_a-test__')
        assert scribify(u'int\xe9rna\xe7ionalization') == str('int_rna_ionalization')


class TestStdoutLogger(object):

    def test_log_line_and_close(self):
        with mock.patch('sys.stdout') as mock_stdout:
            logger = StdoutLogger()
            logger.log_line('stream1', first_line)
            logger.log_line('stream1', second_line)
            logger.close()

        mock_stdout.write.assert_has_calls([
            mock.call('stream1:{0}\n'.format(first_line)),
            mock.call('stream1:{0}\n'.format(second_line))
        ])
        assert mock_stdout.flush.call_count == 1


@pytest.mark.acceptance_suite
class TestCLogMonkLogger(object):

    @pytest.yield_fixture(autouse=True)
    def setup(self):
        self.stream = 'test.stream'
        self.producer = mock.MagicMock()
        loggers.MonkProducer = mock.Mock()
        self.logger = MonkLogger('clog_test_client_id')
        self.logger.report_status = mock.Mock()
        self.logger.producer = self.producer
        self.logger.use_buffer = True
        self.logger.maximum_buffer_bytes = 100 * 1024 * 1024

    @mock.patch('clog.loggers.MonkLogger._log_line_no_size_limit', autospec=True)
    def test_category_name_conversion(self, mock_log_line_no_size_limit):
        line = "content"
        self.logger.log_line(self.stream, line)
        call_1 = mock.call(mock.ANY, "test_stream", line)
        mock_log_line_no_size_limit.assert_has_calls([call_1])

    def test_logger_fine(self):
        self.logger.log_line(self.stream, 'content')
        assert self.producer.send_messages.call_count == 1

    def test_logger_disconnect(self):
        self.producer.send_messages.side_effect = ((), Exception(), Exception())

        for i in range(3):
            self.logger.log_line(self.stream, 'content{}'.format(i))

        assert self.producer.send_messages.call_count == 2
        assert len(self.logger.buffer) == 2

    def test_logger_reconnect(self):
        self.logger.timeout_backoff_s = 0
        self.producer.send_messages.side_effect = (Exception(), (), ())

        self.logger.log_line(self.stream, 'content1')

        assert len(self.logger.buffer) == 1

        self.logger.log_line(self.stream, 'content2')

        assert self.producer.send_messages.call_count == 3
        assert len(self.logger.buffer) == 0

    def test_memory_bytes(self):
        self.producer.send_messages.return_value = True

        assert self.logger.buffer_bytes == 0

        for _ in range(10):
            self.logger._add_to_buffer(self.stream, 'content')

        assert self.logger.buffer_bytes == len('content') * 10

        self.logger._flush_buffer()

        assert self.logger.buffer_bytes == 0

    def test_eviction(self):
        self.logger.maximum_buffer_bytes = 10

        for _ in range(3):
            self.logger._add_to_buffer(self.stream, 'a' * 5)

        assert len(self.logger.buffer) == 2

        self.logger._add_to_buffer(self.stream, 'a' * 15)

        assert len(self.logger.buffer) == 1

    def test_reenqueue(self):
        self.producer.send_messages.side_effect = Exception()

        for i in range(10):
            self.logger.log_line(self.stream, 'content{}'.format(i))

        assert len(self.logger.buffer) == 10
        assert self.producer.send_messages.call_count == 1

        # If the connection is still down, ensure all lines are re-buffered once
        self.logger.last_disconnect = 0
        self.logger._flush_buffer()

        assert len(self.logger.buffer) == 10
        assert self.producer.send_messages.call_count == 2

    def test_buffering_disabled(self):
        self.logger.use_buffer = False
        self.logger.timeout_backoff_s = 0
        self.producer.send_messages.side_effect = Exception()

        for i in range(10):
            self.logger.log_line(self.stream, 'content{}'.format(i))

        assert len(self.logger.buffer) == 0
        assert self.producer.send_messages.call_count == 10
