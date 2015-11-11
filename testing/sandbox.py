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
from __future__ import print_function
from builtins import range
import contextlib
import os
import random
import signal
import socket
import subprocess
import tempfile
import textwrap
import time


def find_open_port(max_tries=16):
    """Find an open port for binding to locally, trying random numbers.
    Unbinds after finding, so there is a possible race condition.
    """
    for i in range(max_tries):
        # choose random port number
        p = random.randrange(1024, 10000)

        # create socket and try to bind to port
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            s.bind(('', p)) # empty string here means INADDR_ANY
        except socket.error:
            raise ValueError('Failed to find open port')

        s.close()
        return p


@contextlib.contextmanager
def scribed_sandbox(port, log_path):
    """Start a scribed in a subprocess, listening on port.

    :param port: the port used to listen on
    :param log_path: directory used to store logs
    :returns: a contextmanager which yiels the subprocess
    """

    config = textwrap.dedent("""
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
        proc = subprocess.Popen(['scribed', '-c', conf_file.name],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

        time.sleep(1)
        yield
    finally:
        os.kill(proc.pid, signal.SIGTERM)
        print(b"\n".join(proc.communicate()).decode('utf8'))
        proc.wait()


def wait_on_condition(func, exc_string, timeout=1, delay=0.1):
    """Wait until a func returns true or there is a timeout.

    :param func: a callable which is called to test a condition
    :param exc_string: the error message to raise if timeout is hit
    :param timeout: max seconds to wait for data
    :param delay: seconds to wait between calling :func:`func`
    """
    end_time = time.time() + timeout
    while time.time() < end_time:
        if func():
            return
        time.sleep(delay)

    raise ValueError(exc_string)


def wait_on_log_data(file_path, expected):
    """Read all the data from a given scribe category logfile and compare
    to expected data.  Poll until matches or timeout reached.

    :param file_path: path to the log file
    """
    def condition():
        try:
            with open(file_path, 'rb') as log_file:
                if log_file.read() == expected:
                    return True
        except IOError:
            return False

    wait_on_condition(condition,
                      "%s did not contain: %r" % (file_path, expected),
                      timeout=3)


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

    cmd = 'tail -F %(filename)s | nc -l -k -p %(port)s' % (
            dict(port=port, filename=log_path))

    try:
        proc = subprocess.Popen(cmd,
                                shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        time.sleep(1)
        yield
    finally:
        os.kill(proc.pid, signal.SIGTERM)
        proc.wait()
