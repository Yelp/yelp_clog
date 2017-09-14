from __future__ import print_function
from __future__ import with_statement

from clog import config

zipkin_plugin_enabled = False
try:
    from py_zipkin.zipkin import zipkin_span
    zipkin_plugin_enabled = True
except ImportError:
    pass


def use_zipkin():
    return zipkin_plugin_enabled and config.use_zipkin


class ZipkinTracing(object):
    """Wrapper class to instrument log_line calls with Zipkin.

    This class is meant to be used if use_zipkin() returns True.
    e.g:
        logger = MyLogger()
        if use_zipkin():
            logger = ZipkinTracing(logger)

    Each call to log_line will add a Zipkin Span and call the underlying
    log_line, all other method call will only call the corresponding method
    of the underlying logger object.

    :param logger: a logger instance, must have a log_line(stream, line) method
    """

    def __init__(self, logger):
        assert use_zipkin()

        self.logger = logger
        self.logger_name = self.logger.__class__.__name__

    def log_line(self, stream, line):
        with zipkin_span(
            service_name='yelp_clog',
            span_name='{name}.log_line {stream}'.format(
                name=self.logger_name,
                stream=stream,
            ),
        ):
            return self.logger.log_line(stream, line)

    def __getattr__(self, item):
        return getattr(self.logger, item)
