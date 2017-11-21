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
Log lines to scribe using the default global logger.
"""

from clog import config
from clog.loggers import FileLogger, get_default_reporter,\
    monk_dependency_installed, MonkLogger, ScribeLogger, StdoutLogger
from clog.zipkin_plugin import use_zipkin, ZipkinTracing

# global logger, used by module-level functions
loggers = None

class LoggingNotConfiguredError(Exception):
    pass


def create_stream_backend_map():
    """PyStaticConfig doesn't support having a map in the configuration,
    so we represent a map as a list, and we use this function to generate
    an actual python dictionary from it."""
    stream_backend_map = {}
    for mapping in config.stream_backend:
        key, value = list(mapping.items())[0]
        stream_backend_map[key] = value
    return stream_backend_map


def check_create_default_loggers():
    """Set up global loggers, if necessary."""
    global loggers

    # important to specifically compare to None, since empty list means something different
    if loggers is None:

        # initialize list of loggers
        loggers = []

        # possibly add logger that writes to local files (for dev)
        if config.clog_enable_file_logging:
            if config.log_dir is None:
                raise ValueError('log_dir not set; set it or disable clog_enable_file_logging')
            loggers.append(FileLogger())

        stream_backend_map = create_stream_backend_map()

        # possibly add logger that writes to scribe
        if not config.scribe_disable:
            logger = ScribeLogger(
                config.scribe_host,
                config.scribe_port,
                config.scribe_retry_interval,
                stream_backend_map=stream_backend_map
            )
            loggers.append(logger)

        if config.clog_enable_stdout_logging:
            loggers.append(StdoutLogger())

        if not config.monk_disable:
            # TODO: this check should be removed once most libraries have
            # been moved to use the "internal" extra-requires.
            if monk_dependency_installed:
                logger = MonkLogger(
                    config.monk_client_id,
                    stream_backend_map=stream_backend_map
                )
                loggers.append(logger)
            else:
                reporter = get_default_reporter()
                reporter(True, "Monk dependency not available. Monk logging will be disabled.")


        if use_zipkin():
            loggers = list(map(ZipkinTracing, loggers))

        if not loggers and not config.is_logging_configured:
            raise LoggingNotConfiguredError


def reset_default_loggers():
    """
    Destroy the global :mod:`clog` loggers. This must be done when forking to
    ensure that children do not share a desynchronized connection to Scribe

    Any writes *after* this call will cause the loggers to be rebuilt, so
    this must be the last thing done before the fork or, better yet, the first
    thing after the fork.
    """
    global loggers

    if loggers:
        for logger in loggers:
            logger.close()
    loggers = None


def log_line(stream, line):
    """Log a single line to the global logger(s). If the line contains
    any newline characters each line will be logged as a separate message.
    If this is a problem for your log you should encode your log messages.

    :param stream: name of the scribe stream to send this log
    :param line: contents of the log message
    """
    check_create_default_loggers()
    for logger in loggers:
        logger.log_line(stream, line)
