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


from contextlib import contextmanager

import threading
import time

try:
    from yelp_meteorite import create_counter
    from yelp_meteorite import create_timer
except ImportError:
    # We'll handle the NameErrors and return a FakeMetric within a try/except
    pass


class FakeMetric(object):
    """Fake Metric object for use when yelp_meteorite isn't available."""
    def count(self, *args, **kwargs):
        pass

    def record(self, *args, **kwargs):
        pass


METRICS_PREFIX = 'yelp_clog.'
METRICS_SAMPLE_PREFIX = METRICS_PREFIX + 'sample.'
METRICS_TOTAL_PREFIX = METRICS_PREFIX + 'total.'
LOG_LINE_SENT = 'log_line.sent'
LOG_LINE_LATENCY = 'log_line.latency_microseconds'
LOG_LINE_MONK_EXCEPTION = 'log_line.monk_exception'
LOG_LINE_MONK_TIMEOUT = 'log_line.monk_timeout'


def _create_or_fake_counter(*args, **kwargs):
    """Create a Counter metric if yelp_meteorite is loaded (passing args), otherwise return a fake
    :return: Counter metric object
    """
    try:
        return create_counter(*args, **kwargs)
    except NameError:
        return FakeMetric()


def _create_or_fake_timer(*args, **kwargs):
    """Create a Timer metric if yelp_meteorite is loaded (passing args), otherwise return a fake
    :return: Timer metric object
    """
    try:
        return create_timer(*args, **kwargs)
    except NameError:
        return FakeMetric()


def _convert_to_microseconds(seconds):
    return 1000000 * seconds


class MetricsReporter(object):
    """Basic metrics reporter that reports on a sampled fraction of requests.
    """

    def __init__(self, backend, sample_rate=0):
        default_dimensions = { 'backend': backend }
        self._sample_counter = 0
        self._sample_log_line_latency = _create_or_fake_timer(
            METRICS_SAMPLE_PREFIX + LOG_LINE_LATENCY,
            default_dimensions
        )
        self._total_log_line_sent = _create_or_fake_counter(
            METRICS_TOTAL_PREFIX + LOG_LINE_SENT,
            default_dimensions
        )
        self._monk_exception_counter = _create_or_fake_counter(
            METRICS_TOTAL_PREFIX + LOG_LINE_MONK_EXCEPTION,
            default_dimensions
        )
        self._monk_timeout_counter = _create_or_fake_counter(
            METRICS_TOTAL_PREFIX + LOG_LINE_MONK_TIMEOUT,
            default_dimensions
        )
        self._sample_rate = sample_rate
        self._lock = threading.RLock()

    @contextmanager
    def sampled_request(self):
        """Context manager that records metrics if it's selected as part of the sample, otherwise runs as usual."""
        sample_request = False
        with self._lock:
            self._sample_counter += 1
            sample_request = self._sample_rate and self._sample_counter % self._sample_rate == 0
        if sample_request:
            start_time = time.time()
            yield  # Do the actual work
            duration = _convert_to_microseconds(time.time() - start_time)
            with self._lock:
                self._total_log_line_sent.count(value=self._sample_counter);
                self._sample_log_line_latency.record(value=duration)
                self._sample_counter = 0
        else:
            yield  # Do the actual work

    def monk_exception(self):
        """Increases the monk exception counter by 1"""
        with self._lock:
            self._monk_exception_counter.count(1)

    def monk_timeout(self):
        """Increases the monk timeout counter by 1"""
        with self._lock:
            self._monk_timeout_counter.count(1)
