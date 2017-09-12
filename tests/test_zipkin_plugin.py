import mock
import pytest

from clog.loggers import MockLogger


def mock_zipkin_span():
    return mock.MagicMock()


@pytest.fixture
def zipkin_plugin():
    import clog.zipkin_plugin

    if not clog.zipkin_plugin.zipkin_plugin_enabled:
        clog.zipkin_plugin.zipkin_span = mock_zipkin_span
    yield clog.zipkin_plugin


@pytest.fixture
def use_zipkin(zipkin_plugin):
    zipkin_plugin.zipkin_plugin_enabled = True
    zipkin_plugin.config.use_zipkin = True
    yield


@pytest.fixture
def no_use_zipkin(zipkin_plugin):
    zipkin_plugin.zipkin_plugin_enabled = False
    yield


class TestZipkinPlugin(object):

    def test_use_zipkin(self, zipkin_plugin, use_zipkin):
        assert zipkin_plugin.use_zipkin()

    def test_no_use_zipkin(self, zipkin_plugin, no_use_zipkin):
        assert not zipkin_plugin.use_zipkin()

    def test_logger_no_use_zipkin(self, zipkin_plugin, no_use_zipkin):
        with pytest.raises(AssertionError):
            zipkin_plugin.ZipkinTracing(MockLogger())

    def test_log_line(self, zipkin_plugin, use_zipkin):
        with mock.patch.object(zipkin_plugin, 'zipkin_span') as zipkin_span:
            logger = zipkin_plugin.ZipkinTracing(MockLogger())
            logger.log_line('stream', 'line')

        assert logger.logger.lines == {'stream': ['line']}
        assert zipkin_span.call_count == 1
        zipkin_span.assert_called_with(
            service_name='yelp_clog',
            span_name='MockLogger.log_line stream',
        )

    def test_other(self, zipkin_plugin, use_zipkin):
        with mock.patch.object(zipkin_plugin, 'zipkin_span') as zipkin_span:
            logger = zipkin_plugin.ZipkinTracing(MockLogger())
            logger.close()

        assert zipkin_span.call_count == 0
