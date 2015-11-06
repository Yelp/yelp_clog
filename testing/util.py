# -*- coding: utf-8 -*-
import os


def create_test_line(extra_size=0):
    line = 'test_line' + 'x' * extra_size
    return line.encode('utf-8')


def get_log_path(logdir, category):
    return os.path.join(logdir, '%s/%s_current' % (category, category))
