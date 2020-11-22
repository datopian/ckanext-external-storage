"""Tests for plugin.py
"""
import ckanext.external_storage.plugin as plugin


def test_plugin():
    p = plugin.ExternalStoragePlugin()
    assert p
