"""Authorization related helpers
"""
import logging

from ckan.plugins import toolkit

from ckanext.authz_service.authz_binding import resource as resource_authz
from ckanext.authz_service.authz_binding.common import get_user_context
from ckanext.authz_service.authzzie import Scope

from . import helpers

log = logging.getLogger(__name__)


def check_object_permissions(id, dataset_id=None, organization_id=None):
    """Check object (resource in storage) permissions

    This wrap's ckanext-authz-service's default logic for checking resource
    by checking for global-prefix/dataset-uuid/* style object scopes.
    """
    if dataset_id and organization_id and organization_id == helpers.storage_namespace():
        log.debug("Requesting authorization for object: %s/%s in namespace %s", dataset_id, id, organization_id)
        dataset = toolkit.get_action('package_show')(get_user_context(), {'id': dataset_id})
        dataset_id = dataset['name']
        try:
            organization_id = dataset['organization']['name']
        except (KeyError, TypeError):
            organization_id = None  # Dataset has no organization
        log.debug("Real resource path is res:%s/%s/%s", organization_id, dataset_id, id)

    return resource_authz.check_resource_permissions(id, dataset_id, organization_id)


def object_id_parser(*args, **kwargs):
    """Object (resource in storage) ID parser
    """
    return resource_authz.resource_id_parser(*args, **kwargs)


def normalize_object_scope(_, granted_scope):
    # type: (Scope, Scope) -> Scope
    """Normalize resource scope by trimming out the org/dataset part and only leaving the sha256

    This helps us deal with cases where a resource is moved (i.e. the dataset is renamed, or the
    organization is renamed, or the dataset is moved to a different organization)
    """
    if not granted_scope:
        return granted_scope

    entity_ref_parts = granted_scope.entity_ref.split('/')

    # let's check that we have a full scope
    if len(entity_ref_parts) < 3:
        return granted_scope
    for part in entity_ref_parts:
        if part is None or part in {'', '*'}:
            return granted_scope

    storage_id = _get_resource_storage_id(organization_id=entity_ref_parts[0],
                                          dataset_id=entity_ref_parts[1],
                                          resource_id=entity_ref_parts[2])
    return Scope(granted_scope.entity_type, storage_id, granted_scope.actions, granted_scope.subscope)


def _get_resource_storage_id(organization_id, dataset_id, resource_id):
    # type: (str, str, str) -> str
    """Get the exact ID of the resource in storage, as opposed to it's ID in CKAN

    A resource in CKAN is identified by <org_id>/<dataset_id>/<resource_id>. However,
    the <org_id> and <dataset_id> can change if the dataset is renamed or moved or the
    organization is renamed. For this reason, we replace the original CKAN ID with a
    "static" ID composed if <lfs_prefix>/<sha256>. <lfs_prefix> in turn is the
    <org_id>/<dataset_id> that the dataset had *when it was originally uploaded*, and
    does not change over time.
    """
    dataset = toolkit.get_action('package_show')(get_user_context(), {'id': dataset_id})
    for res in dataset['resources']:
        if res['id'] == resource_id and res.get('sha256') and res.get('lfs_prefix'):
            return '{}/{}'.format(res['lfs_prefix'], res['sha256'])

    return '{}/{}/{}'.format(organization_id, dataset_id, resource_id)
