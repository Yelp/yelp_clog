# -*- coding: utf-8 -*-
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
from builtins import map

from clog.loggers import ScribeLogger, ScribeIsNotForkSafeError
from clog.global_state import log_line, reset_default_loggers

_pyflakes_ignore = [
    ScribeLogger,
    ScribeIsNotForkSafeError,
    log_line,
    reset_default_loggers,
]

version_info = 2, 2, 9
__version__ = '.'.join(map(str, version_info))
