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
Configuration for :mod:`clog.global_state`. The following configuration
settings are supported:

    **scribe_host**
        (string) hostname of a scribe service used by :func:`clog.log_line`
        to write logs to scribe

    **scribe_port**
        (int) port of the abovementioned scribe service

    **scribe_retry_interval**
        number of seconds to wait before retrying a connection to scribe.
        Used by :func:`clog.log_line` (default 10)

    **log_dir**
        directory used to store files when clog_enable_file_logging is enabled.
        Defaults to the value of $TMPDIR, or `/tmp` if unset

    **scribe_disable**
        disable writing any logs to scribe (default True)

    **scribe_errors_to_syslog**
        flag to enable sending errors to syslog, otherwise to stderr
        (default False)

    **scribe_logging_timeout**
        number of milliseconds to wait on socket connection to scribe server.
        This prevents from being blocked forever on, e.g., writing to scribe
        server. If a write times out, the delivery of the log line is not
        guaranteed and the status of the delivery is unknown; it can be either
        succeeded or failed. For backward compatibility, the old default
        blocking behavior is on when this parameter is left unset or set to 0;
        both the values None and 0 are treated as "infinite".

    **clog_enable_file_logging**
        flag to enable logging to local files. (Default False)

    **clog_enable_stdout_logging**
        flag to enable logging to stdout. Each log line is prefixed with the
        stream name. (Default False)

    **localS3**
        If True, will fetch s3 files directly rather than talking to a service.
"""
import os

import staticconf.config
from staticconf import loader

namespace = 'clog'
clog_namespace = staticconf.NamespaceGetters(namespace)
reloader = staticconf.config.ReloadCallbackChain(namespace)

clog_enable_file_logging = clog_namespace.get_bool('clog_enable_file_logging',
    default=False,
    help="If True, create a FileLogger as the default logger.")

clog_enable_stdout_logging = clog_namespace.get_bool('clog_enable_stdout_logging',
    default=False,
    help="If True, send all log lines to stdout. Defaults to False")

log_dir = clog_namespace.get_string('log_dir',
    default=os.environ.get('TMPDIR', '/tmp'),
    help="Directory to store logs from FileLogger.")

scribe_disable = clog_namespace.get_bool('scribe_disable',
    default=True,
    help="Disable writing logs to scribe.")

scribe_host = clog_namespace.get_string('scribe_host',
    help="Hostname of the scribe server.")

scribe_port = clog_namespace.get_int('scribe_port',
    help="Port of the scribe server.")

scribe_retry_interval = clog_namespace.get_int('scribe_retry_interval',
    default=10,
    help="Seconds to wait between connection retries.")

scribe_errors_to_syslog = clog_namespace.get_bool('scribe_errors_to_syslog',
    default=False,
    help="If True, send Scribe errors to syslog, otherwise to stderr")

scribe_logging_timeout = clog_namespace.get_int('scribe_logging_timeout',
    default=1000,
    help="Milliseconds to time out scribe logging")

localS3 = clog_namespace.get_bool('localS3',
    default=False,
    help='If True, will fetch s3 files directly rather than talking to a service')

use_kafka = clog_namespace.get_bool('use_kafka',
    default=False,
    help='If True, will tail from a stream via a service talking to Kafka')

is_logging_configured = False


def configure_from_dict(config_dict):
    """Configure the :mod:`clog` package from a dictionary.

    :param config_dict: a dict of config data
    """
    staticconf.DictConfiguration(config_dict, namespace=namespace)
    reloader()

    global is_logging_configured
    is_logging_configured = True


def configure_from_object(config_obj):
    """Configure the :mod:`clog` package from an object (or module).

    :param config_obj: an object or module with config attributes
    """
    loader.ObjectConfiguration(config_obj, namespace=namespace)
    reloader()

    global is_logging_configured
    is_logging_configured = True


def configure(scribe_host, scribe_port, **kwargs):
    """Configure the :mod:`clog` package from arguments.

    :param scribe_host: the scribe service hostname
    :param scribe_port: the scribe service port
    :param kwargs: other configuration parameters
    """
    kwargs['scribe_host'] = scribe_host
    kwargs['scribe_port'] = scribe_port
    staticconf.DictConfiguration(kwargs, namespace=namespace)
    reloader()

    global is_logging_configured
    is_logging_configured = True
