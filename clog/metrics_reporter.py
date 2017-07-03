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

    def start(self, *args, **kwargs):
        pass

    def stop(self, *args, **kwargs):
        pass


METRICS_PREFIX = 'yelp_clog.'
METRICS_SAMPLE_PREFIX = METRICS_PREFIX + 'sample.'
METRICS_TOTAL_PREFIX = METRICS_PREFIX + 'total.'
LOG_LINE_SENT = 'log_line.sent'
LOG_LINE_LATENCY = 'log_line.latency'


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


class MetricsReporter(object):
    """Basic metrics reporter that reports on a sampled fraction of requests.

    Not thread-safe, thus is called from within the context of ScribeLogger's existing RLock.
    """

    _sample_counter = 0
    _sample_log_line_sent = _create_or_fake_counter(METRICS_SAMPLE_PREFIX + LOG_LINE_SENT)
    _sample_log_line_latency = _create_or_fake_timer(METRICS_SAMPLE_PREFIX + LOG_LINE_LATENCY)
    _total_log_line_sent = _create_or_fake_counter(METRICS_TOTAL_PREFIX + LOG_LINE_SENT)

    def __init__(self, sample_rate=0):
        self._sample_rate = sample_rate

    @contextmanager
    def sampled_request(self):
        """Context manager that records metrics if it's selected as part of the sample, otherwise runs as usual."""
        self._sample_counter += 1
        if self._sample_rate and self._sample_counter % self._sample_rate == 0:
            self._total_log_line_sent.count(value=self._sample_counter);
            self._sample_counter = 0
            self._sample_log_line_latency.start()
            yield  # Do the actual work
            self._sample_log_line_latency.stop()
            self._sample_log_line_sent.count()
        else:
            yield  # Do the actual work
