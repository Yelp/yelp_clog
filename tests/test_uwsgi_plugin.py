from testing.sandbox import install_fake_uwsgi
install_fake_uwsgi()


import clog.uwsgi_plugin
import marshal
import mock
import pickle


def test_uwsgi_handle_msg_header():
    clog_msg = (('abc', '123'), {})
    pickle_data = pickle.dumps(clog_msg)
    marshal_data = clog.uwsgi_plugin.MSG_HEADER + marshal.dumps(clog_msg)
    with mock.patch('clog.uwsgi_plugin._orig_log_line') as orig_line:
        with mock.patch('clog.uwsgi_plugin.mule_msg_dispatcher') as dispatcher:
            clog.uwsgi_plugin._plugin_mule_msg_shim(pickle_data)
            dispatcher.assert_called_with(pickle_data)
            clog.uwsgi_plugin._plugin_mule_msg_shim(marshal_data)
            orig_line.assert_called_with(*clog_msg[0], **clog_msg[1])


def test_uwsgi_default_over_max_size():
    big_string = 's' * 65536
    assert clog.uwsgi_plugin._mule_msg('blah', big_string) == False


def test_uwsgi_default_on_failed_mule_msg():
    with mock.patch('clog.uwsgi_plugin._orig_log_line') as orig_line:
        with mock.patch('clog.uwsgi_plugin._mule_msg', return_value=False):
            clog.uwsgi_plugin.uwsgi_log_line('blah', 'test_message')
            orig_line.assert_called_with('blah', 'test_message')


def test_uwsgi_mule_msg_header_apply():
    # for some reason python3 marshal serializes arguments
    # differently when their handled via expansion/compaction
    def build_serialized(*args, **kwargs):
        kwargs.pop('mule', None)
        return clog.uwsgi_plugin.MSG_HEADER + marshal.dumps((args, kwargs))

    args = ('test_stream', 'test_line')
    kwargs = {}
    expected_serialized = build_serialized(*args, **kwargs)
    with mock.patch('uwsgi.mule_msg') as mm:
        clog.uwsgi_plugin._mule_msg(*args, **kwargs)
        mm.assert_called_with(expected_serialized)


def test_uwsgi_mule_msg_header_apply_with_mule():
    # for some reason python3 marshal serializes arguments
    # differently when their handled via expansion/compaction
    def build_serialized(*args, **kwargs):
        kwargs.pop('mule', None)
        return clog.uwsgi_plugin.MSG_HEADER + marshal.dumps((args, kwargs))

    args = ('test_stream', 'test_line')
    kwargs = {'mule': 1}
    expected_serialized = build_serialized(*args, **kwargs)
    with mock.patch('uwsgi.mule_msg') as mm:
        clog.uwsgi_plugin._mule_msg(*args, **kwargs)
        mm.assert_called_with(expected_serialized, 1)
