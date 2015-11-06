# -*- coding: utf-8 -*-
import clog

# check that we're not accidentally testing the packaged clog
assert not clog.__file__.startswith('/usr')
