import marshal
import mock
import pickle
import pytest
import sys


@pytest.fixture(scope='module')
def uwsgi_plugin():

    class uwsgi(object):
        mule_msg_hook = None

        @staticmethod
        def mule_msg(message, mule=None):
            pass

        @staticmethod
        def mule_msg_recv_size():
            return 65536

    class uwsgidecorators(object):
        @staticmethod
        def mule_msg_dispatcher(message):
            pass

    sys.modules['uwsgi'] = uwsgi
    sys.modules['uwsgidecorators'] = uwsgidecorators
    import clog.uwsgi_plugin

    yield clog.uwsgi_plugin
    sys.modules.pop('uwsgi')
    sys.modules.pop('uwsgidecorators')


@pytest.mark.usefixtures('uwsgi_plugin')
class TestUwsgiPlugin(object):

    def test_uwsgi_handle_msg_header(self, uwsgi_plugin):
        clog_msg = (('abc', '123'), {})
        pickle_data = pickle.dumps(clog_msg)
        marshal_data = uwsgi_plugin.MSG_HEADER + marshal.dumps(clog_msg)
        with mock.patch.object(uwsgi_plugin, '_orig_log_line') as orig_line:
            with mock.patch.object(uwsgi_plugin, 'mule_msg_dispatcher') as dispatcher:
                uwsgi_plugin._plugin_mule_msg_shim(pickle_data)
                dispatcher.assert_called_with(pickle_data)
                uwsgi_plugin._plugin_mule_msg_shim(marshal_data)
                orig_line.assert_called_with(*clog_msg[0], **clog_msg[1])


    def test_uwsgi_default_over_max_size(self, uwsgi_plugin):
        big_string = 's' * 65536
        assert uwsgi_plugin._mule_msg('blah', big_string) == False


    def test_uwsgi_default_on_failed_mule_msg(self, uwsgi_plugin):
        with mock.patch.object(uwsgi_plugin, '_orig_log_line') as orig_line:
            with mock.patch.object(uwsgi_plugin, '_mule_msg', return_value=False):
                uwsgi_plugin.uwsgi_log_line('blah', 'test_message')
                orig_line.assert_called_with('blah', 'test_message')


    def test_uwsgi_mule_msg_header_apply(self, uwsgi_plugin):
        # for some reason python3 marshal serializes arguments
        # differently when they're handled via expansion/compaction
        def build_serialized(*args, **kwargs):
            kwargs.pop('mule', None)
            return uwsgi_plugin.MSG_HEADER + marshal.dumps((args, kwargs))

        args = ('test_stream', 'test_line')
        kwargs = {}
        expected_serialized = build_serialized(*args, **kwargs)
        with mock.patch('uwsgi.mule_msg') as mm:
            uwsgi_plugin._mule_msg(*args, **kwargs)
            mm.assert_called_with(expected_serialized)


    def test_uwsgi_mule_msg_header_apply_with_mule(self, uwsgi_plugin):
        # for some reason python3 marshal serializes arguments
        # differently when they're handled via expansion/compaction
        def build_serialized(*args, **kwargs):
            kwargs.pop('mule', None)
            return uwsgi_plugin.MSG_HEADER + marshal.dumps((args, kwargs))

        args = ('test_stream', 'test_line')
        kwargs = {'mule': 1}
        expected_serialized = build_serialized(*args, **kwargs)
        with mock.patch('uwsgi.mule_msg') as mm:
            uwsgi_plugin._mule_msg(*args, **kwargs)
            mm.assert_called_with(expected_serialized, 1)
