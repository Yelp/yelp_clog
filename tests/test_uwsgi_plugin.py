import mock
import pickle
import pytest
import six
import struct
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
    sys.modules.pop('clog.uwsgi_plugin')
    del clog.handlers.UwsgiHandler

    with pytest.raises(ImportError):
        import clog.uwsgi_plugin


@pytest.mark.usefixtures('uwsgi_plugin')
class TestUwsgiPlugin(object):

    def test_uwsgi_handle_valid_msg(self, uwsgi_plugin):
        message = ('this is a fake stream', 'this is a fake line!')
        mule_msg_data = uwsgi_plugin._encode_mule_msg(*message)
        with mock.patch.object(uwsgi_plugin, '_orig_log_line') as orig_line:
            with mock.patch.object(uwsgi_plugin, 'mule_msg_dispatcher') as dispatcher:
                uwsgi_plugin._plugin_mule_msg_shim(mule_msg_data)
                orig_line.assert_called_with(*map(six.b, message))
                assert not dispatcher.called

    def test_uwsgi_handle_invalid_msg_pass_thru(self, uwsgi_plugin):
        message = ('this is a fake stream', 'this is a fake line!')
        pickle_data = pickle.dumps(message)
        with mock.patch.object(uwsgi_plugin, '_orig_log_line') as orig_line:
            with mock.patch.object(uwsgi_plugin, 'mule_msg_dispatcher') as dispatcher:
                uwsgi_plugin._plugin_mule_msg_shim(pickle_data)
                dispatcher.assert_called_with(pickle_data)
                assert not orig_line.called

    def test_uwsgi_default_over_max_size(self, uwsgi_plugin):
        big_string = 's' * 65536
        assert uwsgi_plugin._mule_msg('blah', big_string) == False

    def test_uwsgi_default_on_failed_mule_msg(self, uwsgi_plugin):
        with mock.patch.object(uwsgi_plugin, '_orig_log_line') as orig_line:
            with mock.patch.object(uwsgi_plugin, '_mule_msg', return_value=False):
                uwsgi_plugin.uwsgi_log_line('blah', 'test_message')
                orig_line.assert_called_with('blah', 'test_message')

    def test_uwsgi_mule_msg_header_apply(self, uwsgi_plugin):
        args = ('test_stream', 'test_line')
        kwargs = {}
        expected_serialized = uwsgi_plugin._encode_mule_msg(*args)
        with mock.patch('uwsgi.mule_msg') as mm:
            uwsgi_plugin._mule_msg(*args, **kwargs)
            mm.assert_called_with(expected_serialized)

    def test_uwsgi_mule_msg_header_apply_with_mule(self, uwsgi_plugin):
        args = ('test_stream', 'test_line')
        kwargs = {'mule': 1}
        expected_serialized = uwsgi_plugin._encode_mule_msg(*args)
        with mock.patch('uwsgi.mule_msg') as mm:
            uwsgi_plugin._mule_msg(*args, **kwargs)
            mm.assert_called_with(expected_serialized, 1)

    def test_decode_mule_msg_exc_tag(self, uwsgi_plugin):
        stream = b'test stream'
        line = b'test line'
        msg = struct.pack(uwsgi_plugin.ENCODE_FMT, b'blah', len(stream), len(line)) + stream + line
        with pytest.raises(ValueError):
            uwsgi_plugin._decode_mule_msg(msg)

    def test_decode_mule_msg_exc_len(self, uwsgi_plugin):
        stream = b'test_stream'
        line = b'test line'
        msg = struct.pack(uwsgi_plugin.ENCODE_FMT, uwsgi_plugin.HEADER_TAG, len(stream), len(line)-1) + stream + line
        with pytest.raises(ValueError):
            uwsgi_plugin._decode_mule_msg(msg)
