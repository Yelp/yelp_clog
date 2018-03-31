# -*- coding: utf-8 -*-
# Copyright 2018 Yelp Inc.
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
import mock
import pytest

from monk.producers import monk_thrift
from monk.producers import StreamNotFoundError

from clog import config
from clog import loggers
from clog.loggers import MonkLogger


class TestSchematizerIntegration(object):

    @pytest.yield_fixture(autouse=True)
    def setup_config(self):
        config.configure_from_dict({'use_schematizer': True})
        self.stream = 'test.stream'
        loggers.MonkProducer = mock.Mock(autospec=True)
        loggers.MetricsReporter = mock.MagicMock(autospec=True)
        self.logger = MonkLogger('clog_test_client_id')
        self.logger.schematizer_client = mock.Mock(autospec=True)
        self.logger.report_status = mock.Mock()

    @pytest.yield_fixture
    def stream_not_found_error(self):
        result = monk_thrift.PartitionCountResult(
            value=0,
            errorCause=None,
            resultCode=monk_thrift.ResultCode.STREAM_NOT_FOUND
        )
        yield StreamNotFoundError(self.stream, [("Not Found", result)])

    def test_register_schema_call(self, stream_not_found_error):
        self.logger.producer.send_messages.side_effect = [stream_not_found_error, None]
        line = "content"
        self.logger.log_line(self.stream, line)

        calls = [mock.call('test_stream', [line], None)] * 2
        self.logger.producer.send_messages.assert_has_calls(calls)
        self.logger.schematizer_client.register_schema_from_schema_json.assert_called_once_with(
            namespace='scribe_log',
            source='test_stream',
            schema_json={
                "type": "record",
                "namespace": "scribe_log",
                "name": 'test_stream',
                "doc": ("This schema is not used to actually serialize or deserialize messages,"
                        "but stream will be assigned to this schema."),
                "fields": [
                    {"type": "string", "name": "log_line", "doc": "log line string"}
                ]
            },
            source_owner_email='notavailable@yelp.com',
            contains_pii=False,
            cluster_type='scribe',
            stream_policy='best_effort',
        )

    def test_prevent_deep_recursion(self, stream_not_found_error):
        line = "content"
        self.logger.producer.send_messages.side_effect = stream_not_found_error
        self.logger.log_line(self.stream, line)

    def test_schematizer_exception(self, stream_not_found_error):
        self.logger.producer.send_messages.side_effect = stream_not_found_error
        self.logger.schematizer_client.register_schema_from_schema_json.side_effect = Exception('Error')
        line = "content"
        self.logger.log_line(self.stream, line)

    def test_existing_schema(self):
        line = "content"
        self.logger.log_line(self.stream, line)

        calls = [mock.call('test_stream', [line], None)]
        self.logger.producer.send_messages.assert_has_calls(calls)
        self.logger.schematizer_client.register_schema_from_schema_json.assert_not_called()

    def test_stream_not_found_without_schematizer(self, stream_not_found_error):
        config.configure_from_dict({'use_schematizer': False})
        self.logger = MonkLogger('clog_test_client_id')
        self.logger.report_status = mock.Mock()
        line = "content"
        self.logger.producer.send_messages.side_effect = stream_not_found_error
        self.logger.log_line(self.stream, line)
        self.logger.report_status.called_once()
