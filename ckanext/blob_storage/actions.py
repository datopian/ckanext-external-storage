"""External Storage API actions
"""
import ast
import logging
from typing import Any, Dict, Optional

from ckan.plugins import toolkit
from giftless_client import LfsClient
from giftless_client.exc import LfsError

from . import helpers

log = logging.getLogger(__name__)


@toolkit.side_effect_free
def get_resource_download_spec(context, data_dict):
    """Get a signed URL from LFS server to download a resource
    """
    resource = _get_resource(context, data_dict)
    for k in ('lfs_prefix', 'sha256', 'size'):
        if k not in resource:
            return {}

    return get_lfs_download_spec(context, resource)


def get_lfs_download_spec(context,  # type: Dict[str, Any]
                          resource,  # type: Dict[str, Any]
                          sha256=None,  # type: Optional[str]
                          size=None,  # type: Optional[int]
                          filename=None,  # type: Optional[str]
                          storage_prefix=None  # type: Optional[str]
                          ):  # type: (...) -> Dict[str, Any]
    """Get the LFS download spec (URL and headers) for a resource

    This function allows overriding the expected sha256 and size for situations where
    an additional file is associated with a CKAN resource and we want to override it.
    In these cases, we will use the parent resource for authorization checks and
    sha256 and size to request an object from the LFS server. You should *only* use
    these override arguments if you know what you are doing, as allowing client side
    code to override the sha256 and size could lead to potential security issues.
    """
    if storage_prefix is None:
        storage_prefix = resource['lfs_prefix']
    if size is None:
        size = resource['size']
    if sha256 is None:
        sha256 = resource['sha256']
    if filename is None:
        filename = helpers.resource_filename(resource)

    package = toolkit.get_action('package_show')(context, {'id': resource['package_id']})
    authz_token = get_download_authz_token(context, package['organization']['name'], package['name'], resource['id'])
    client = context.get('download_lfs_client', LfsClient(helpers.server_url(), authz_token))

    resources = [{"oid": sha256, "size": size, "x-filename": filename}]
    object_spec = _get_resource_download_lfs_objects(client, storage_prefix, resources)[0]

    assert object_spec['oid'] == sha256
    assert object_spec['size'] == size

    if 'error' in object_spec:
        raise toolkit.ObjectNotFound('Object error [{}]: {}'.format(object_spec['error'].get('message', '[no message]'),
                                                                    object_spec['error'].get('code', 'unknown')))

    return object_spec['actions']['download']


@toolkit.side_effect_free
def resource_schema_show(context, data_dict):
    """Get a resource schema as a dictionary instead of string
    """
    resource = _get_resource(context, data_dict)

    if resource.get('schema', False):
        try:
            return ast.literal_eval(resource['schema'])
        except ValueError:
            return resource['schema']
    return {}


@toolkit.side_effect_free
def resource_sample_show(context, data_dict):
    """Get a resource sample as a list of dictionaries instead of string
    """
    resource = _get_resource(context, data_dict)

    if resource.get('sample', False):
        try:
            return ast.literal_eval(resource['sample'])
        except ValueError:
            return resource['sample']
    return {}


def _get_resource_download_lfs_objects(client, lfs_prefix, resources):
    """Get LFS download operation response objects for a given resource list
    """
    log.debug("Requesting download spec from LFS server for %s", resources)
    try:
        batch_response = client.batch(lfs_prefix, 'download', resources)
    except LfsError as e:
        if e.status_code == 404:
            raise toolkit.ObjectNotFound("The requested resource does not exist")
        elif e.status_code == 422:
            raise toolkit.ObjectNotFound("Object parameters mismatch")
        elif e.status_code == 403:
            raise toolkit.ObjectNotFound("Request was denied by the LFS server")
        else:
            raise

    return batch_response['objects']


def get_download_authz_token(context, org_name, package_name, resource_id):
    # type: (Dict[str, Any], str, str, str) -> str
    """Get an authorization token for getting the download URL from LFS
    """
    authorize = toolkit.get_action('authz_authorize')
    if not authorize:
        raise RuntimeError("Cannot find authz_authorize; Is ckanext-authz-service installed?")

    scope = helpers.resource_authz_scope(package_name, org_name=org_name, actions='read', resource_id=resource_id)
    log.debug("Requesting authorization token for scope: %s", scope)
    authz_result = authorize(context, {"scopes": [scope]})
    if not authz_result or not authz_result.get('token', False):
        raise RuntimeError("Failed to get authorization token for LFS server")
    log.debug("Granted scopes: %s", authz_result['granted_scopes'])

    if len(authz_result['granted_scopes']) == 0:
        raise toolkit.NotAuthorized("You are not authorized to download this resource")

    return authz_result['token']


def _get_resource(context, data_dict):
    """Get resource by ID
    """
    if 'resource' in data_dict:
        return data_dict['resource']
    return toolkit.get_action('resource_show')(context, {'id': data_dict['id']})
