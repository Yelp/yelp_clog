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
"""
:mod:`clog` is a package for handling log data. It can be used for the
following:


Python Logging Handler
---------------------------------

:class:`clog.handlers.ScribeHandler` can be used to send standard python
:mod:`logging` to a scribe stream.


Logging Operational and Mission Critical Data
---------------------------------------------

:func:`clog.loggers.ScribeLogger.log_line` can be used to log mission critical,
machine readable, and opertional data to scribe. There is also a global
:func:`clog.log_line` which has the same purpose but requires global
configuration (see :mod:`clog.config`). Use of the global is discouraged.


Reading Scribe Logs
-------------------

:mod:`clog.readers` provides classes for reading scribe logs locally or
from a server.

"""

from __future__ import absolute_import

from clog.loggers import ScribeLogger, ScribeIsNotForkSafeError
from clog.global_state import log_line, reset_default_loggers

uwsgi_plugin_enabled = False
try:
    from clog.uwsgi_plugin import uwsgi_patch_global_state, uwsgi_log_line
    uwsgi_plugin_enabled = True
except ImportError:
    pass

_pyflakes_ignore = [
    ScribeLogger,
    ScribeIsNotForkSafeError,
    log_line,
    reset_default_loggers,
] + ([
    uwsgi_patch_global_state,
    uwsgi_log_line,
] if uwsgi_plugin_enabled else [])

