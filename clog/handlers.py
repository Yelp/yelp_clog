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
:class:`logging.Handler` objects which can be used to send standard python
logging to a scribe stream.

"""

import logging

from clog.loggers import MonkLogger
from clog.loggers import ScribeLogger
from clog.utils import scribify
from clog.zipkin_plugin import use_zipkin, ZipkinTracing
from clog import global_state


DEFAULT_FORMAT = '%(process)s\t%(asctime)s\t%(name)-12s %(levelname)-8s: %(message)s'


class CLogHandler(logging.Handler):
    """
    .. deprecated:: 0.1.6

    .. warning::

        Use ScribeHandler if you want to log to scribe, or a
        :class:`logging.handlers.FileHandler` to log to a local file.

    Handler for the standard logging library that logs to clog.
    """

    def __init__(self, stream, logger=None):
        'If no logger is specified, the global one is used'
        logging.Handler.__init__(self)
        self.stream = stream
        if logger is not None and use_zipkin():
            logger = ZipkinTracing(logger)
        self.logger = logger or global_state

    def emit(self, record):
        try:
            msg = self.format(record)
            self.logger.log_line(self.stream, msg)
        except Exception:
            raise
        except:
            self.handleError(record)


class ScribeHandler(logging.Handler):
    """Handler for sending python standard logging messages to a scribe
    stream.

    .. code-block:: python

        import clog.handlers, logging
        log = logging.getLogger(name)
        log.addHandler(clog.handlers.ScribeHandler('localhost', 3600, 'stream', retry_interval=3))


    :param host: hostname of scribe server
    :param port: port number of scribe server
    :param stream: name of the scribe stream logs will be sent to
    :param retry_interval: default 0, number of seconds to wait between retries
    """

    def __init__(self, host, port, stream, retry_interval=0):
        logging.Handler.__init__(self)
        self.stream = stream
        self.logger = ScribeLogger(host, port, retry_interval)
        if use_zipkin():
            self.logger = ZipkinTracing(self.logger)

    def emit(self, record):
        try:
            msg = self.format(record)
            self.logger.log_line(self.stream, msg)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class MonkHandler(logging.Handler):
    """Handler for sending python standard logging messages to a monk
        stream.

        .. code-block:: python

            import clog.handlers, logging
            log = logging.getLogger(name)
            log.addHandler(clog.handlers.MonkHandler('client_id', 'localhost', 3600, 'stream'))


        :param client_id: client id to identify the user logging
        :param stream: name of the monk stream logs will be sent to
        :param host: hostname of monk server
        :param port: port number of monk server
        """

    def __init__(self, client_id, stream, host=None, port=None):
        logging.Handler.__init__(self)
        self.stream = stream
        self.logger = MonkLogger(client_id, host, port)

    def emit(self, record):
        try:
            msg = self.format(record)
            self.logger.log_line(self.stream, msg)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


def add_logger_to_scribe(logger, log_level=logging.INFO, fmt=DEFAULT_FORMAT, clogger_object=None):
    """Sets up a logger to log to scribe.

    By default, messages at the INFO level and higher will go to scribe.

    .. deprecated:: 0.1.6

    .. warning::

        This function is deprecated in favor of using :func:`clog.log_line` or
        :class:`ScribeHandler` directly.

    :param logger: A logging.Logger instance
    :param log_level: The level to log at
    :param clogger_object: for use in testing
    """
    scribified_name = scribify(logger.name)
    if any (h.stream == scribified_name for h in logger.handlers if isinstance(h, CLogHandler)):
        return
    clog_handler = CLogHandler(scribified_name, logger=clogger_object)
    clog_handler.setLevel(log_level)
    clog_handler.setFormatter(logging.Formatter(fmt))
    logger.setLevel(log_level)
    logger.addHandler(clog_handler)


def get_scribed_logger(log_name, *args, **kwargs):
    """Get/create a logger and adds it to scribe.

    .. deprecated:: 0.1.6

    .. warning::

        This function is deprecated in favor of using :func:`clog.log_line`
        directly.

    :param log_name: name of log to write to using logging.getLogger
    :param args, kwargs: passed to add_logger_to_scribe
    :returns: a :class:`logging.Logger`
    """
    log = logging.getLogger(log_name)
    add_logger_to_scribe(log, *args, **kwargs)
    return log
