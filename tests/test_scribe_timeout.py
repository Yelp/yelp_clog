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
from contextlib import contextmanager

import mock
import pytest
import staticconf.testing
from thriftpy.transport.socket import TSocket

from clog import config
from clog.loggers import ScribeLogger


HOST = 'localhost'
PORT = 1234
RETRY = 100


class TestScribeLoggerTimeout(object):

    @pytest.yield_fixture(autouse=True)
    def setup_config(self):
        with staticconf.testing.MockConfiguration(
            namespace=config.namespace,
        ) as self.mock_config:
            yield

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
