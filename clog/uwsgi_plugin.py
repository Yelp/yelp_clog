import uwsgi
import uwsgidecorators
import logging
import clog
import clog.global_state
import clog.handlers
import six.moves.cPickle as pickle


def _mule_msg(*args, **kwargs):
    mule = kwargs.pop('mule', 1)
    data = pickle.dumps({
        'service': 'uwsgi_mulefunc',
        'func': 'log_line',
        'args': args,
        'kwargs': kwargs,
    })
    # Unfortunately this check has to come after the pickling
    # unless we just want to make a conservative guess
    if len(data) > max_recv_size:
        return False
    return uwsgi.mule_msg(data, mule)


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


def uwsgi_log_line(stream, line, mule=1):
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
# 1. Register 'log_line' in all mules for dispatch handling on the mule side
# 2. Insert 'UwsgiHandler' into the clog.handlers module for seamless usage
# 3. Store reference to the original global_state.log_line for fallback
# 4. Fetch mule_msg_recv_size to calculate send limit

uwsgidecorators.mule_functions['log_line'] = clog.global_state.log_line
setattr(clog.handlers, 'UwsgiHandler', UwsgiHandler)
_orig_log_line = clog.global_state.log_line
# See https://github.com/unbit/uwsgi/pull/1487
max_recv_size = getattr(uwsgi, 'mule_msg_recv_size', lambda: 65536)()
