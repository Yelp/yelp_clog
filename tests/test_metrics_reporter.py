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

    @mock.patch('clog.metrics_reporter.MetricsReporter._sample_log_line_sent.count', autospec=True)
    def test_metrics_reporter_sampling(self, mock_sample_log_line_sent_count):
        metrics = MetricsReporter(sample_rate=3)

        assert metrics._sample_counter == 0
        # First try, not part of sample
        with metrics.sampled_request():
            assert not mock_sample_log_line_sent_count.called
            assert metrics._sample_counter == 1
        assert not mock_sample_log_line_sent_count.called

        # Second try, not part of sample
        with metrics.sampled_request():
            assert not mock_sample_log_line_sent_count.called
            assert metrics._sample_counter == 2
        assert not mock_sample_log_line_sent_count.called

        # Third try, part of sample, so called outside the context
        with metrics.sampled_request():
            assert not mock_sample_log_line_sent_count.called
            assert metrics._sample_counter == 0
        assert mock_sample_log_line_sent_count.call_count == 1

    @mock.patch('clog.metrics_reporter.MetricsReporter._sample_log_line_sent.count', autospec=True)
    def test_zero_sample_rate(self, mock_sample_log_line_sent_count):
        metrics = MetricsReporter(sample_rate=0)
        assert metrics._sample_counter == 0
        # Should never sample
        with metrics.sampled_request():
            assert not mock_sample_log_line_sent_count.called
            assert metrics._sample_counter == 1
        assert not mock_sample_log_line_sent_count.called

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
        metrics = MetricsReporter(sample_rate=1)
        # Monkeypatch in the fake counters
        metrics._sample_log_line_sent = FakeMetric()
        metrics._sample_log_line_latency = FakeMetric()
        metrics._total_log_line_sent = FakeMetric()

        assert metrics._sample_counter == 0
        # First try, not part of sample
        with metrics.sampled_request():
            assert metrics._sample_counter == 0

