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

import clog
from clog import config, global_state, loggers
from clog.global_state import create_preferred_backend_map
from clog.global_state import check_create_default_loggers

SCRIBE_CONFIG = {
    "scribe_disable": False,
    "scribe_host": "1.2.3.4",
    "scribe_port": "1234",
}

SCRIBE_MONK_CONFIG = {
    "scribe_disable": False,
    "scribe_host": "1.2.3.4",
    "scribe_port": "1234",
    "monk_disable": False,
}


class TestGlobalState(object):

    @pytest.yield_fixture(autouse=True)
    def setup_config(self):
        with staticconf.testing.MockConfiguration(
            namespace=config.namespace,
        ) as self.mock_config:
            yield

    @pytest.fixture(autouse=True)
    def setup_loggers(self):
        global_state.reset_default_loggers()

    def test_create_preferred_backend_map(self):
        config.configure_from_dict({
           "preferred_backend_map": [
               {"stream1": "scribe"},
               {"stream2": "monk"},
               {"stream3": "dual"},
           ]
        })
        expected = {
            "stream1": "scribe",
            "stream2": "monk",
            "stream3": "dual",
        }
        assert create_preferred_backend_map() == expected

    def test_global_state_scribe_only(self):
        config.configure_from_dict(SCRIBE_CONFIG)
        check_create_default_loggers()
        assert len(global_state.loggers) == 1
        assert isinstance(global_state.loggers[0], loggers.ScribeLogger)

    def test_global_state_monk_and_scribe(self):
        config.configure_from_dict(SCRIBE_MONK_CONFIG)
        global_state.monk_dependency_installed = True
        clog.loggers.MonkProducer = mock.Mock()
        check_create_default_loggers()
        assert len(global_state.loggers) == 1
        assert isinstance(global_state.loggers[0], loggers.ScribeMonkLogger)

    def test_global_state_monk_not_installed(self):
        config.configure_from_dict(SCRIBE_MONK_CONFIG)
        global_state.monk_dependency_installed = False
        clog.loggers.MonkProducer = mock.Mock()
        check_create_default_loggers()
        assert len(global_state.loggers) == 1
        assert isinstance(global_state.loggers[0], loggers.ScribeLogger)
