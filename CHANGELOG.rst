Release Notes
=============

master
------

* Use scribify function to convert MonkLogger stream names, for
  backward compatibility with ScribeLogger.

2.14.0
------

* Add close() method to MonkLogger

2.13.0
------

* When creating a ScribeTailer instance, fall back to find_tail_host() if no tail service host
  is specified and the configuration is not set.
* Implement size limit for MonkLogger (5MB)

2.12.1
------

* Fix a compatiblity issue where gzipped logs weren't decompresser correctly in python 3.

2.12.0
------

* Change reader configuration file path (from /etc/yelp_clog.json to /nail/srv/configs/yelp_clog.json)

2.11.0
------

* Prevent exceptions if Monk is enabled but not installed

2.6.2
-----

* Remove references to yelp_lib

2.6.1
-----

* Add type checking to ``MockLogger`` log_line function

2.6.0
-----

* Make StreamTailer connection message more flexible
* Drop py33 and add py35

2.5.2
-----

* Fix FileLogger when using python3

2.5.1
-----

* Fix use of unicode

2.5.0
-----

* Use six instead of future

2.4.4
-----

* Fix ``ScribeHandler`` under Python 3.

2.4.3
-----

* Fix tail/nc process leaks during testing.

2.4.2
-----

* Improvements to testing.
* Fix ``scribify`` function under Python 3.

2.4.1
-----
* Remove the thriftpy hard-pinning. Compatible now with thriftpy 0.1+ and 0.2+.

2.4.0
-----
* Add clog_enable_stdout_logging config option to dump log lines to stdout.
  Defaults to false.

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
