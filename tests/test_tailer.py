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
import codecs
import itertools
import os
import shutil
import socket
import tempfile
import time

import pytest
import mock
import six

from clog import readers, loggers
from testing import sandbox


TEST_STREAM_PREFIX = 'tmp_clog_package_unittest_'


def get_nonce_str(num_bytes=16):
    return codecs.encode(os.urandom(num_bytes), 'hex_codec').decode('ascii')


def wait_on_lines(tailer, num_lines=10, timeout=15, delay=0.1):
    """Tail the scribe service, get `num_lines` from stream `stream`."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            return list(itertools.islice(iter(tailer), num_lines))
        except socket.error:
            time.sleep(0.1)


@pytest.mark.acceptance_suite
class TestStreamTailerAcceptance(object):

    @pytest.yield_fixture(autouse=True)
    def setup_sandbox(self):
        scribe_logdir = tempfile.mkdtemp()
        self.stream = TEST_STREAM_PREFIX + get_nonce_str(8)
        scribed_port = sandbox.find_open_port()
        tailer_port = sandbox.find_open_port()

        log_path = os.path.join(scribe_logdir,
                                '%s/%s_current' % (self.stream, self.stream))

        self.tailer = readers.StreamTailer(
                self.stream,
                add_newlines=False,
                automagic_recovery=False,
                timeout=0.2,
                host='localhost',
                port=tailer_port)

        self.logger = loggers.ScribeLogger('localhost', scribed_port, 10)

        with sandbox.scribed_sandbox(scribed_port, scribe_logdir):
            with sandbox.tailer_sandbox(tailer_port, log_path):
                yield
        shutil.rmtree(scribe_logdir)

    def test_log_and_tail(self):
        nonce = get_nonce_str()
        num_lines, read_lines = 10, 8
        lines = ["%s %d" % (nonce, i) for i in range(num_lines)]
        for line in lines:
            self.logger.log_line(self.stream, line)

        encoded_lines = [line.encode('utf8') for line in lines]
        result = wait_on_lines(self.tailer, read_lines)
        assert result == encoded_lines[:read_lines]

    def test_unicode(self):
        eszett_str = get_nonce_str() + " " + u'\xdf'
        assert isinstance(eszett_str, six.text_type)

        for _ in range(10):
            self.logger.log_line(self.stream, eszett_str)

        eszett_str_utf8 = eszett_str.encode('UTF-8')

        lines = wait_on_lines(self.tailer, 1)
        assert lines == [eszett_str_utf8]

@mock.patch('clog.readers.get_settings')
def test_find_tail_host(mock_settings):
    mock_settings.return_value = {}
    assert readers.find_tail_host('fakehost') == 'fakehost'

def test_construct_conn_msg_without_lines():
    conn_msg = readers.construct_conn_msg("streamA")
    assert conn_msg == 'streamA\n'

def test_construct_conn_msg_with_lines():
    conn_msg = readers.construct_conn_msg('streamA', lines=2)
    assert conn_msg == 'streamA 2\n'

def test_tail_lines_with_options():
    conn_msg = readers.construct_conn_msg(
            'streamA',
            protocol_opts={'opt1': 'value1', 'opt2': 'value2'})
    assert conn_msg.startswith('streamA opt')
    assert conn_msg.endswith('\n')
    assert ' opt1=value1' in conn_msg
    assert ' opt2=value2' in conn_msg
    assert len(conn_msg) == 32

def test_tail_lines_with_lines_and_options():
    conn_msg = readers.construct_conn_msg(
            'streamA',
            lines=10,
            protocol_opts={'opt1': 'value1', 'opt2': 'value2'})
    assert conn_msg.startswith('streamA 10')
    assert conn_msg.endswith('\n')
    assert ' opt1=value1' in conn_msg
    assert ' opt2=value2' in conn_msg
    assert len(conn_msg) == 35

def get_settings_side_effect(*args, **kwargs):
    if args[0] == 'DEFAULT_SCRIBE_TAIL_HOST':
        return 'scribe.local.yelpcorp.com'
    elif args[0] == 'HOST_TO_TAIL_HOST':
        return {'scribe.local.yelpcorp.com': 'local'}
    elif args[0] == 'REGION_TO_TAIL_HOST':
        return {'region1': 'tail-host1.prod.yelpcorp.com'}
    elif args[0] == 'ECOSYSTEM_TO_TAIL_HOST':
        return {'eco1': 'tail-host2.dev.yelpcorp.com'}


@mock.patch('clog.readers.get_settings')
@mock.patch('clog.readers.get_ecosystem_from_file')
@mock.patch('clog.readers.get_region_from_file')
def test_find_tail_host_prod(mock_region, mock_ecosystem, mock_settings):
    mock_ecosystem.return_value = 'prod'
    mock_region.return_value = 'region1'
    mock_settings.side_effect = get_settings_side_effect
    assert readers.find_tail_host() == readers.find_tail_host('scribe.local.yelpcorp.com') == 'tail-host1.prod.yelpcorp.com'


@mock.patch('clog.readers.get_settings')
@mock.patch('clog.readers.get_ecosystem_from_file')
def test_find_tail_host_devb(mock_ecosystem, mock_settings):
    mock_ecosystem.return_value = 'eco1'
    mock_settings.side_effect = get_settings_side_effect
    assert readers.find_tail_host() == readers.find_tail_host('scribe.local.yelpcorp.com') == 'tail-host2.dev.yelpcorp.com'
