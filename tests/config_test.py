# -*- coding: utf-8 -*-
from staticconf.testing import MockConfiguration
import testifycompat as T

from clog import config


class BlankObject(object):
    pass


class TestConfigure(object):

    @T.setup
    def setup_config(self):
        self.mock_config = MockConfiguration(namespace=config.namespace)
        self.mock_config.__enter__()

    @T.teardown
    def teardown_config(self):
        self.mock_config.__exit__()

    def test_configure_from_dict(self):
        config_data = {
            'scribe_host': 'example.com',
            'scribe_port': '5555'
        }
        config.configure_from_dict(config_data)
        T.assert_equal(config.scribe_host, config_data['scribe_host'])

    def test_configure_from_object(self):
        config_obj = BlankObject()
        config_obj.scribe_host = 'example.com',
        config_obj.scribe_port = 5555
        config.configure_from_object(config_obj)
        T.assert_equal(config.scribe_port, 5555)

    def test_configure(self):
        config.configure('what', '111', scribe_disable=True)
        T.assert_equal(config.scribe_port, 111)
        T.assert_equal(config.scribe_host, 'what')
        T.assert_equal(config.scribe_disable, True)

