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
import clog.global_state
from clog import config

class TestGlobalState(object):

    def test_global_state(self):
        clog.log_line('foo', {})
        assert clog.global_state.loggers is None
        config_data = {
            'clog_enable_stdout_logging': True,
        }
        config.configure_from_dict(config_data)
        clog.log_line('foo', {})
        assert clog.global_state.loggers is not None
