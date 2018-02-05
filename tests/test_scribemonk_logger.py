# -*- coding: utf-8 -*-
# Copyright 2018 Yelp Inc.
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
import mock
import pytest

import staticconf.testing

from clog import config
from clog.loggers import ScribeMonkLogger


class TestScribeMonkLogger(object):

    @pytest.yield_fixture(autouse=True)
    def setup_config(self):
        with staticconf.testing.MockConfiguration(
            namespace=config.namespace,
        ) as self.mock_config:
            yield

    @mock.patch('clog.loggers.MonkLogger', autospec=True)
    @mock.patch('clog.loggers.ScribeLogger', autospec=True)
    def test_preferred_backend_monk(self, scribe_logger, monk_logger):
        config.configure_from_dict({'preferred_backend': 'monk'})
        logger = ScribeMonkLogger(config, scribe_logger, monk_logger)

        logger.log_line('stream', 'line')

        assert not scribe_logger.log_line.called
        assert monk_logger.log_line.called

    @mock.patch('clog.loggers.MonkLogger', autospec=True)
    @mock.patch('clog.loggers.ScribeLogger', autospec=True)
    def test_preferred_backend_scribe(self, scribe_logger, monk_logger):
        config.configure_from_dict({'preferred_backend': 'scribe'})
        logger = ScribeMonkLogger(config, scribe_logger, monk_logger)

        logger.log_line('stream', 'line')

        assert scribe_logger.log_line.called
        assert not monk_logger.log_line.called

    @mock.patch('clog.loggers.MonkLogger', autospec=True)
    @mock.patch('clog.loggers.ScribeLogger', autospec=True)
    def test_backend_map(self, scribe_logger, monk_logger):
        preferred_backend_map = {
            'stream1': 'monk',
            'stream2': 'scribe',
            'stream3': 'dual',
        }
        logger = ScribeMonkLogger(
            config,
            scribe_logger,
            monk_logger,
            preferred_backend_map
        )
        logger.log_line('stream1', 'line1')
        logger.log_line('stream2', 'line2')
        logger.log_line('stream3', 'line3')
        logger.log_line('stream4', 'line4')

        monk_logger.log_line.assert_has_calls([
            mock.call('stream1', 'line1'),
            mock.call('stream3', 'line3')
        ])
        scribe_logger.log_line.assert_has_calls([
            mock.call('stream2', 'line2'),
            mock.call('stream3', 'line3'),
            mock.call('stream4', 'line4')
        ])
