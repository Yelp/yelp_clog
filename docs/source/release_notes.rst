

Release Notes
=============

1.4.0
-----

* Switched to thriftpy, a third-party Thrift implementation.

* Now compatible with Python 3.3+ and PyPy2.

1.3.0
-----

* Add an enforcement on the size of scribe log lines. Log lines are expected to
  be less than 5MB; they are processed as normal. For log lines with size
  between 5MB and 50MB, warnings are issued by logging them additionaly to the
  scribe log "tmp_who_clog_large_line". Any line over 50 MB is treated as an
  error, and the exception LogLineIsTooLongError is raised.

1.2.0
-----

* The logging_timeout argument of loggers.ScribeLogger is added. This allows
  scribe logging to timeout instead of being blocked if the scribe server is
  non-responding promptly; this benefits the applications prioritizing user
  experience over logging.

1.1.4
-----

* The _recv_compressed method of StreamTailer and the python-snappy dependency
  have been removed. Now it's no more possible to automatically decompress a
  snappy-compressed stream.

1.0.0
-----

This is a major release as it breaks backwards compatibility.

* Many imports were removed from the top level :mod:`clog` namespace. They are
  still available from the full module name (ex: :mod:`clog.loggers`,
  :mod:`clog.config`, etc)
* Configuration defaults have changed. The default is now to log to a local
  file in `/tmp`, instead of raising a ValueError if scribe is not configured.
  Note this only applies to :func:`clog.log_line`
