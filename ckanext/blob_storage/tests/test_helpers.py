import pytest
from ckan.tests import factories

from ckanext.blob_storage import helpers


@pytest.mark.ckan_config('ckanext.blob_storage.storage_service_url', 'https://foo.example.com/lfs')
def test_server_url_from_config():
    assert 'https://foo.example.com/lfs' == helpers.server_url()


@pytest.mark.ckan_config('ckanext.blob_storage.storage_service_url', 'https://foo.example.com/lfs/')
def test_server_url_strip_trailing_slash():
    assert 'https://foo.example.com/lfs' == helpers.server_url()


def test_resource_storage_prefix_explicit_org():
    prefix = helpers.resource_storage_prefix('mypackage', 'myorg')
    assert 'myorg/mypackage' == prefix


@pytest.mark.usefixtures('clean_db', 'reset_db')
@pytest.mark.ckan_config('ckanext.blob_storage.storage_namespace', 'some-namespace')
def test_resource_storage_prefix_unspecified_org():
    prefix = helpers.resource_storage_prefix('mypackage')
    assert 'some-namespace/mypackage' == prefix


@pytest.mark.usefixtures('clean_db', 'reset_db')
@pytest.mark.ckan_config('ckanext.blob_storage.storage_namespace', 'some-namespace')
def test_resource_storage_prefix_no_org():
    factories.Dataset(name='mypackage')
    prefix = helpers.resource_storage_prefix('mypackage')
    assert 'some-namespace/mypackage' == prefix


def test_resource_authz_scope_default_actions():
    scope = helpers.resource_authz_scope('mypackage', org_name='myorg')
    assert 'obj:myorg/mypackage/*:read,write' == scope


def test_resource_authz_scope_custom_actions():
    scope = helpers.resource_authz_scope('mypackage', actions='read', org_name='myorg')
    assert 'obj:myorg/mypackage/*:read' == scope


@pytest.mark.ckan_config('ckanext.blob_storage.storage_namespace', 'some-namespace')
def test_resource_authz_scope_default_namespace():
    scope = helpers.resource_authz_scope('mypackage')
    assert 'obj:some-namespace/mypackage/*:read,write' == scope


@pytest.mark.ckan_config('ckanext.blob_storage.storage_namespace', None)
def test_resource_authz_scope_no_configured_namespace():
    scope = helpers.resource_authz_scope('mypackage')
    assert 'obj:ckan/mypackage/*:read,write' == scope
