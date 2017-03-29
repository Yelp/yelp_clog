import uwsgi
import logging
import clog
import clog.global_state
import clog.handlers
import marshal
from uwsgidecorators import mule_msg_dispatcher

MSG_HEADER = b'clog'

def _mule_msg(*args, **kwargs):
    mule = kwargs.pop('mule', None)
    data = MSG_HEADER + marshal.dumps((args, kwargs))
    # Unfortunately this check has to come after the marshalling
    # unless we just want to make a conservative guess
    if len(data) > max_recv_size:
        return False
    # Either deliver to a specific mule msg queue
    # or the shared queue which will be handled by
    # the first available mule (yay!)
    if mule:
        return uwsgi.mule_msg(data, mule)
    return uwsgi.mule_msg(data)

def _plugin_mule_msg_shim(message):
    if message[:len(MSG_HEADER)] == MSG_HEADER:
        args, kwargs = marshal.loads(message[len(MSG_HEADER):])
        return _orig_log_line(*args, **kwargs)
    else:
        return mule_msg_dispatcher(message)


class UwsgiHandler(logging.Handler):

    def __init__(self, stream, mule=1):
        logging.Handler.__init__(self)
        self.stream = stream
        self.mule = mule

    def emit(self, record):
        try:
            msg = self.format(record)
            _mule_msg(self.stream, msg, mule=self.mule)
        except Exception:
            raise
        except:
            self.handleError(record)


def uwsgi_log_line(stream, line, mule=None):
    # Explicit 'False' check - see https://github.com/unbit/uwsgi/pull/1482
    # We don't want to double-emit on 'None' response if we have older uwsgi
    if _mule_msg(stream, line, mule=mule) == False:
        _orig_log_line(stream, line)


def uwsgi_patch_global_state():
    map(
        lambda x: setattr(x, 'log_line', uwsgi_log_line),
        (clog, clog.global_state)
    )


# Couple setup tasks at import:
# 1. Insert 'UwsgiHandler' into the clog.handlers module for seamless usage
# 2. Store reference to the original global_state.log_line for fallback
# 3. Override the plugin mule_msg_hook call to intercept our messages*
# 4. Fetch mule_msg_recv_size to calculate send limit
#
# * By default the uwsgidecorators module installs its own hook to dispatch
# messages formatted by its decorator objects. We could insert into this dispatch
# map and use them, however using 'marshal' over 'cPickle' provides another 3x+
# speedup on the critical path - and since we're delivering this data to a literal
# fork of the python interp, there's not concern about data compatibility. Our
# shim will try to 'marshal.loads' and if we fail just pass it along to the
# uwsgidecorators dispatcher.

setattr(clog.handlers, 'UwsgiHandler', UwsgiHandler)
_orig_log_line = clog.global_state.log_line
# It's vital that no other module override this hook after we have done so.
# This is an unfortunate consequence of the uwsgi_python plugin but the
# hook implementation isn't naturally exstensible - we're managing here by
# making assumptions about the environment, one of which is that uwsgidecorators
# is the only other module installing to this hook.
uwsgi.mule_msg_hook = _plugin_mule_msg_shim
# See https://github.com/unbit/uwsgi/pull/1487
max_recv_size = getattr(uwsgi, 'mule_msg_recv_size', lambda: 65536)()
