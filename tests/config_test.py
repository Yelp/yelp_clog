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
from staticconf.testing import MockConfiguration
import testifycompat as T

from clog import config


class BlankObject(object):
    pass


class TestConfigure(object):

    @T.setup
    def setup_config(self):
        self.mock_config = MockConfiguration(namespace=config.namespace)
        self.mock_config.__enter__()

    @T.teardown
    def teardown_config(self):
        self.mock_config.__exit__()

    def test_configure_from_dict(self):
        config_data = {
            'scribe_host': 'example.com',
            'scribe_port': '5555'
        }
        config.configure_from_dict(config_data)
        T.assert_equal(config.scribe_host, config_data['scribe_host'])

    def test_configure_from_object(self):
        config_obj = BlankObject()
        config_obj.scribe_host = 'example.com',
        config_obj.scribe_port = 5555
        config.configure_from_object(config_obj)
        T.assert_equal(config.scribe_port, 5555)

    def test_configure(self):
        config.configure('what', '111', scribe_disable=True)
        T.assert_equal(config.scribe_port, 111)
        T.assert_equal(config.scribe_host, 'what')
        T.assert_equal(config.scribe_disable, True)

