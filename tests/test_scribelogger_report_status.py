# -*- coding: utf-8 -*-
import shutil
import tempfile

import mock
from testifycompat import setup_teardown

from clog.loggers import ScribeLogger
from testing.sandbox import find_open_port
from testing.sandbox import scribed_sandbox
from testing.util import get_log_path


class TestCLogScribeReportStatus(object):

    @setup_teardown
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

    def test_exception_in_raise_status(self):
        """Make sure socket is closed if exception is raised in report_status function."""

        def raise_exception_on_error(is_error, message):
            if is_error:
                raise Exception(message)

        self.logger.report_status = raise_exception_on_error
        self.logger.client.Log = mock.Mock(side_effect=IOError)

        try:
            self.logger.log_line(self.stream, '12345678')
        except Exception:
            assert not self.logger.connected
