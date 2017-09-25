# -*- coding: utf-8 -*-
# Copyright 2017 Yelp Inc.
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

import pytest
import mock

from clog.metrics_reporter import FakeMetric
from clog.metrics_reporter import MetricsReporter


@pytest.mark.acceptance_suite
class TestMetricsReporter(object):

    def test_metrics_reporter_sampling(self):
        metrics = MetricsReporter(backend="test", sample_rate=3)

        assert metrics._sample_counter == 0
        # First try, not part of sample
        with metrics.sampled_request():
            assert metrics._sample_counter == 1

        # Second try, not part of sample
        with metrics.sampled_request():
            assert metrics._sample_counter == 2

        # Third try, part of sample, so called outside the context
        with metrics.sampled_request():
            assert metrics._sample_counter == 3
        assert metrics._sample_counter == 0

    def test_zero_sample_rate(self):
        metrics = MetricsReporter(backend="test", sample_rate=0)
        assert metrics._sample_counter == 0
        # Should never sample
        with metrics.sampled_request():
            assert metrics._sample_counter == 1

    @mock.patch('clog.metrics_reporter.create_counter', create=True, side_effect=NameError)
    def test_fake_counter_creation(self, mock_create_counter):
        from clog.metrics_reporter import _create_or_fake_counter
        assert type(_create_or_fake_counter("my_counter")) is FakeMetric
        assert mock_create_counter.call_count == 1

    @mock.patch('clog.metrics_reporter.create_timer', create=True, side_effect=NameError)
    def test_fake_timer_creation(self, mock_create_timer):
        from clog.metrics_reporter import _create_or_fake_timer
        assert type(_create_or_fake_timer("my_timer")) is FakeMetric
        assert mock_create_timer.call_count == 1

    def test_fake_metric_functionality(self):
        metrics = MetricsReporter(backend="test", sample_rate=1)
        # Monkeypatch in the fake counters
        metrics._sample_log_line_latency = FakeMetric()
        metrics._total_log_line_sent = FakeMetric()

        assert metrics._sample_counter == 0
        # First try, not part of sample
        with metrics.sampled_request():
            assert metrics._sample_counter == 1
        assert metrics._sample_counter == 0

    def test_latency_microseconds(self):
        metrics = MetricsReporter(backend="test", sample_rate=1)
        metrics._sample_log_line_latency = mock.Mock(FakeMetric())
        with metrics.sampled_request():
            pass
        assert metrics._sample_log_line_latency.record.call_count == 1
        # time.time() has a resolution of down to half a microsecond, so seeing under that means we're tracking s or ms.
        assert metrics._sample_log_line_latency.record.call_args[1]['value'] > 0.1
