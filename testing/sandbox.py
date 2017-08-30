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
from __future__ import print_function
import contextlib
import os
import signal
import socket
import subprocess
import tempfile
import textwrap
import time


def find_open_port():
    """Bind to an ephemeral port, force it into the TIME_WAIT state, and
    unbind it.

    This means that further ephemeral port alloctions won't pick this
    "reserved" port, but subprocesses can still bind to it explicitly, given
    that they use SO_REUSEADDR.

    By default on linux you have a grace period of 60 seconds to reuse this
    port.

    To check your own particular value:
    $ cat /proc/sys/net/ipv4/tcp_fin_timeout
    60
    """
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', 0))
    s.listen(1)

    sockname = s.getsockname()

    # these three are necessary just to get the port into a TIME_WAIT state
    s2 = socket.socket()
    s2.connect(sockname)
    s.accept()

    return sockname[1]


@contextlib.contextmanager
def scribed_sandbox(port, log_path):
    """Start a scribed in a subprocess, listening on port.

    :param port: the port used to listen on
    :param log_path: directory used to store logs
    :returns: a contextmanager which yiels the subprocess
    """

    config = textwrap.dedent("""\
        port={port}
        <store>
        category=default
        type=file
        max_write_interval=1
        file_path={file_path}
        </store>
    """.format(port=port, file_path=log_path)).encode('ascii')

    conf_file = tempfile.NamedTemporaryFile()
    conf_file.write(config)
    conf_file.flush()

    try:
        proc = subprocess.Popen(
            ('scribed', '-c', conf_file.name),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(1)
        yield
    finally:
        os.kill(proc.pid, signal.SIGTERM)
        print(b"\n".join(proc.communicate()).decode('utf8'))
        proc.wait()


def wait_on_condition(func, timeout, delay=0.1):
    """Wait until a func returns true or there is a timeout.

    :param func: a callable which raises AssertionError until it passes
    :param timeout: max seconds to wait for data
    :param delay: seconds to wait between calling :func:`func`
    """
    end_time = time.time() + timeout
    while True:
        try:
            ret = func()
            if ret is not None:
                raise ValueError(ret)
            return
        except AssertionError:
            if time.time() > end_time:
                raise
        time.sleep(delay)


def wait_on_log_data(file_path, expected):
    """Read all the data from a given scribe category logfile and compare
    to expected data.  Poll until matches or timeout reached.

    :param file_path: path to the log file
    """
    def check_log_file_contents():
        try:
            with open(file_path, 'rb') as log_file:
                assert expected in log_file.read()
        except IOError:
            raise AssertionError('{0} does not exist!'.format(file_path))

    wait_on_condition(check_log_file_contents, timeout=3)


@contextlib.contextmanager
def tailer_sandbox(port, log_path):
    """Start a log tailing service in a subprocess.

    :param port: the port used to listen on
    :param log_path: path to a log file
    """

    # Touch file to make sure it's there
    os.mkdir(os.path.dirname(log_path))
    with open(log_path, 'a+'):
        pass

    cmd = (
        'dumb-init', 'bash', '-c',
        'tail -F {filename} | nc -l -k -p {port}'.format(
            filename=log_path, port=port,
        )
    )

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        time.sleep(1)
        yield
    finally:
        os.kill(proc.pid, signal.SIGTERM)
        proc.wait()
