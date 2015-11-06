# -*- coding: utf-8 -*-
from contextlib import contextmanager

import mock
import staticconf.testing
import testifycompat as T
from thriftpy.transport.socket import TSocket

from clog import config
from clog.loggers import ScribeLogger


HOST = 'localhost'
PORT = 1234
RETRY = 100


class TestScribeLoggerTimeout(object):

    @T.setup
    def setup_config(self):
        self.mock_config = staticconf.testing.MockConfiguration(namespace=config.namespace)
        self.mock_config.__enter__()

    @T.teardown
    def teardown_config(self):
        self.mock_config.__exit__()

    @contextmanager
    def construct_scribelogger_with_mocked_tsocket(self, timeout=None):
        with mock.patch('thriftpy.transport.socket.TSocket', spec=TSocket):
            if timeout is None:
                yield ScribeLogger(HOST, PORT, RETRY)
            else:
                yield ScribeLogger(HOST, PORT, RETRY, logging_timeout=timeout)

    def test_unset_logging_timeout_with_global_conf_set(self):
        config.configure_from_dict({'scribe_logging_timeout': 100})
        with self.construct_scribelogger_with_mocked_tsocket() as mock_logger:
            mock_logger.socket.set_timeout.assert_called_once_with(100)

    def test_unset_logging_timeout_with_global_conf_unset(self):
        with self.construct_scribelogger_with_mocked_tsocket() as mock_logger:
            mock_logger.socket.set_timeout.assert_called_once_with(1000)

    def test_logging_timeout_set_0_overwrite_global_conf(self):
        config.configure_from_dict({'scribe_logging_timeout': 100})
        with self.construct_scribelogger_with_mocked_tsocket(timeout=0) as mock_logger:
            assert not mock_logger.socket.set_timeout.called

    def test_logging_timeout_set_arbitrary(self):
        with self.construct_scribelogger_with_mocked_tsocket(timeout=20) as mock_logger:
            mock_logger.socket.set_timeout.assert_called_once_with(20)
