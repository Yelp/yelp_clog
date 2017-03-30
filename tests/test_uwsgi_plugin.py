import mock
import os
import pickle
import pytest
import six
import struct
import sys

MASTERPID = os.getpid()
POLLUTE = os.environ.get('POLLUTE')


def install_fake_uwsgi():
    if not POLLUTE:
        assert os.getpid() != MASTERPID

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

    if not 'uwsgi' in sys.modules:
        sys.modules['uwsgi'] = uwsgi
        sys.modules['uwsgidecorators'] = uwsgidecorators


def run(target):

    def _waitpid_for_status(pid):
        return (os.waitpid(pid, 0)[1] & 0xFF00) >> 8

    if not POLLUTE:
        pid = os.fork()
        if not pid:
            install_fake_uwsgi()
            import clog.uwsgi_plugin
            try:
                target(clog.uwsgi_plugin)
            except Exception:
                os._exit(1)
            os._exit(0)

        assert _waitpid_for_status(pid) == 0
    else:
        install_fake_uwsgi()
        import clog.uwsgi_plugin
        target(clog.uwsgi_plugin)


class TestUwsgiPlugin(object):

    def test_baseline(self):
        def target(uwsgi_plugin):
            assert False

        with pytest.raises(AssertionError):
            run(target)

    def test_uwsgi_handle_valid_msg(self):
        def target(uwsgi_plugin):
            message = ('this is a fake stream', 'this is a fake line!')
            mule_msg_data = uwsgi_plugin._encode_mule_msg(*message)
            with mock.patch.object(uwsgi_plugin, '_orig_log_line') as orig_line:
                with mock.patch.object(uwsgi_plugin, 'mule_msg_dispatcher') as dispatcher:
                    uwsgi_plugin._plugin_mule_msg_shim(mule_msg_data)
                    orig_line.assert_called_with(*map(six.b, message))
                    assert not dispatcher.called

        run(target)

    def test_uwsgi_handle_invalid_msg_pass_thru(self):
        def target(uwsgi_plugin):
            message = ('this is a fake stream', 'this is a fake line!')
            pickle_data = pickle.dumps(message)
            with mock.patch.object(uwsgi_plugin, '_orig_log_line') as orig_line:
                with mock.patch.object(uwsgi_plugin, 'mule_msg_dispatcher') as dispatcher:
                    uwsgi_plugin._plugin_mule_msg_shim(pickle_data)
                    dispatcher.assert_called_with(pickle_data)
                    assert not orig_line.called

        run(target)

    def test_uwsgi_default_over_max_size(self):
        def target(uwsgi_plugin):
            big_string = 's' * 65536
            assert uwsgi_plugin._mule_msg('blah', big_string) == False

        run(target)

    def test_uwsgi_default_on_failed_mule_msg(self):
        def target(uwsgi_plugin):
            with mock.patch.object(uwsgi_plugin, '_orig_log_line') as orig_line:
                with mock.patch.object(uwsgi_plugin, '_mule_msg', return_value=False):
                    uwsgi_plugin.uwsgi_log_line('blah', 'test_message')
                    orig_line.assert_called_with('blah', 'test_message')

        run(target)

    def test_uwsgi_mule_msg_header_apply(self):
        def target(uwsgi_plugin):
            args = ('test_stream', 'test_line')
            kwargs = {}
            expected_serialized = uwsgi_plugin._encode_mule_msg(*args)
            with mock.patch('uwsgi.mule_msg') as mm:
                uwsgi_plugin._mule_msg(*args, **kwargs)
                mm.assert_called_with(expected_serialized)

        run(target)

    def test_uwsgi_mule_msg_header_apply_with_mule(self):
        def target(uwsgi_plugin):
            args = ('test_stream', 'test_line')
            kwargs = {'mule': 1}
            expected_serialized = uwsgi_plugin._encode_mule_msg(*args)
            with mock.patch('uwsgi.mule_msg') as mm:
                uwsgi_plugin._mule_msg(*args, **kwargs)
                mm.assert_called_with(expected_serialized, 1)

        run(target)

    def test_decode_mule_msg_tag_error(self):
        def target(uwsgi_plugin):
            stream = b'test stream'
            line = b'test line'
            msg = struct.pack(uwsgi_plugin.ENCODE_FMT, b'blah', len(stream), len(line)) + stream + line
            with pytest.raises(ValueError):
                uwsgi_plugin._decode_mule_msg(msg)

        run(target)

    def test_decode_mule_msg_len_error(self):
        def target(uwsgi_plugin):
            stream = b'test_stream'
            line = b'test line'
            msg = struct.pack(uwsgi_plugin.ENCODE_FMT, uwsgi_plugin.HEADER_TAG, len(stream), len(line) - 1) + stream + line
            with pytest.raises(ValueError):
                uwsgi_plugin._decode_mule_msg(msg)

        run(target)
