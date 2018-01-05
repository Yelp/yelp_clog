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

monk_disable = clog_namespace.get_bool('monk_disable',
    default=True,
    help="Disable writing logs to monk.")

default_backend = clog_namespace.get_string('default_backend',
    default="scribe",
    help="The default backend to use (can be 'scribe', 'monk' or 'dual')")

stream_backend = clog_namespace.get_list('stream_backend',
    default=[],
    help="The map of stream names to backend ('scribe', 'monk' or 'dual'). "
    "If not specified, the default one will be used. The mapping must be "
    "represente as a list using the format\n"
    "    - stream_name: backend_name"
)

monk_client_id = clog_namespace.get_string('monk_client_id',
    default="clog",
    help="Identification for user writing to monk")

monk_stream_prefix = clog_namespace.get_string('monk_stream_prefix',
    default="",
    help="This prefix will be added to all the streams being produced to Monk.")

monk_timeout_ms = clog_namespace.get_int('monk_timeout_ms',
    default=100,
    help=("Timeout while writing to Monk. After a timeout occurs, "
          "clog won't write to Monk for `monk_timeout_backoff_ms`, then it "
          "will try again."))

monk_timeout_backoff_ms = clog_namespace.get_int('monk_timeout_backoff_ms',
    default=2000,
    help=("After a timeout occurs, clog won't write to Monk for as many "
          "milliseconds as defined here"))

scribe_host = clog_namespace.get_string('scribe_host',
    help="Hostname of the scribe server.")

scribe_port = clog_namespace.get_int('scribe_port',
    help="Port of the scribe server.")

default_scribe_tail_port = clog_namespace.get_int('default_scribe_tail_port',
    default=3535,
    help="Default port of scribe tailing services.")

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

use_zipkin = clog_namespace.get_bool('use_zipkin',
    default=False,
    help='Whether to instrument loggers .log_line method with Zipkin.')

metrics_sample_rate = clog_namespace.get_int('metrics_sample_rate',
    default=0,
    help='Number of messages to sample to emit one latency metric.')

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
