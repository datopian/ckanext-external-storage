import errno
import logging
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Tuple

import requests
from ckan.lib.cli import CkanCommand
from ckan.lib.helpers import _get_auto_flask_context  # noqa  we need this for Flask request context
from ckan.model import Resource, Session, User
from ckan.plugins import toolkit
from flask import Response
from giftless_client import LfsClient
from giftless_client.types import ObjectAttributes
from six import binary_type, string_types
from sqlalchemy.orm import load_only
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.wsgi import FileWrapper

from ckanext.blob_storage import helpers
from ckanext.blob_storage.download_handler import call_download_handlers


def _log():
    return logging.getLogger(__name__)


class MigrateResourcesCommand(CkanCommand):
    """Migrate all non-migrated resources to external blob storage
    """
    summary = __doc__.split('\n')[0]
    usage = __doc__
    min_args = 0

    _user = None
    _max_failures = 3
    _retry_delay = 3

    def command(self):
        self._load_config()
        self._user = User.get(self.site_user['name'])
        with app_context() as context:
            context.g.user = self.site_user['name']
            context.g.userobj = self._user
            self.migrate_all_resources()

    def migrate_all_resources(self):
        """Do the actual migration
        """
        migrated = 0
        failed = 0
        for resource_obj in get_unmigrated_resources():
            _log().info("Starting to migrate resource %s", resource_obj.id)
            try:
                self.migrate_resource(resource_obj)
                _log().info("Finished migrating resource %s", resource_obj.id)
                migrated += 1
            except Exception:
                _log().exception("Failed to migrate resource %s", resource_obj.id)
                failed += 1
                if failed >= self._max_failures:
                    _log().error("Skipping resource after %d failures", failed)
                    failed = 0
                    continue
                time.sleep(self._retry_delay)

        _log().info("Finished migrating %d resources", migrated)

    def migrate_resource(self, resource_obj):
        # type: (Resource) -> None
        dataset, resource_dict = get_resource_dataset(resource_obj)
        resource_name = helpers.resource_filename(resource_dict)

        with download_resource(resource_dict, dataset) as resource_file:
            _log().debug("Starting to upload file: %s", resource_file)
            lfs_namespace = helpers.storage_namespace()
            props = self.upload_resource(resource_file, dataset['id'], lfs_namespace, resource_name)
            props['lfs_prefix'] = '{}/{}'.format(lfs_namespace, dataset['id'])
            props['sha256'] = props.pop('oid')
            _log().debug("Upload complete; sha256=%s, size=%d", props['sha256'], props['size'])

        update_storage_props(resource_obj, props)

    def upload_resource(self, resource_file, dataset_id, lfs_namespace, filename):
        # type: (str, str, str, str) -> ObjectAttributes
        """Upload a resource file to new storage using LFS server
        """
        token = self.get_upload_authz_token(dataset_id)
        lfs_client = LfsClient(helpers.server_url(), token)
        with open(resource_file, 'rb') as f:
            props = lfs_client.upload(f, lfs_namespace, dataset_id, filename=filename)

        # Only return standard object attributes
        return {k: v for k, v in props.items() if k[0:2] != 'x-'}

    def get_upload_authz_token(self, dataset_id):
        # type: (str) -> str
        """Get an authorization token to upload the file to LFS
        """
        authorize = toolkit.get_action('authz_authorize')
        if not authorize:
            raise RuntimeError("Cannot find authz_authorize; Is ckanext-authz-service installed?")

        context = {'ignore_auth': True, 'auth_user_obj': self._user}
        scope = helpers.resource_authz_scope(dataset_id, actions='write')
        authz_result = authorize(context, {"scopes": [scope]})

        if not authz_result or not authz_result.get('token', False):
            raise RuntimeError("Failed to get authorization token for LFS server")

        if len(authz_result['granted_scopes']) == 0:
            raise toolkit.NotAuthorized("You are not authorized to upload resources")

        return authz_result['token']


def update_storage_props(resource, lfs_props):
    # type: (Resource, Dict[str, Any]) -> None
    """Update the resource with new storage properties
    """
    resource.extras['lfs_prefix'] = lfs_props['lfs_prefix']
    resource.extras['sha256'] = lfs_props['sha256']
    resource.size = lfs_props['size']
    flag_modified(resource, 'extras')


@contextmanager
def download_resource(resource, dataset):
    # type: (Dict[str, Any], Dict[str, Any]) -> str
    """Download the resource to a local file and provide the file name

    This is a context manager that will delete the local file once context is closed
    """
    resource_file = tempfile.mktemp(prefix='ckan-blob-migration-')
    try:
        response = call_download_handlers(resource, dataset)
        if response.status_code == 200:
            _save_downloaded_response_data(response, resource_file)
        elif response.status_code in {301, 302}:
            _save_redirected_response_data(response, resource_file)
        else:
            raise RuntimeError("Unexpected download response code: {}".format(response.status_code))
        yield resource_file
    finally:
        try:
            os.unlink(resource_file)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise


def _save_downloaded_response_data(response, file_name):
    # type: (Response, str) -> None
    """Get an HTTP response object with open file containing a resource and save the data locally
    to a temporary file
    """
    with open(file_name, 'wb') as f:
        if isinstance(response.response, (string_types, binary_type)):
            _log().debug("Response contains inline string data, saving to %s", file_name)
            f.write(response.response)
        elif isinstance(response.response, FileWrapper):
            _log().debug("Response is a werkzeug.wsgi.FileWrapper, copying to %s", file_name)
            for chunk in response.response:
                f.write(chunk)
        elif hasattr(response.response, 'read'):  # assume an open stream / file
            _log().debug("Response contains an open file object, copying to %s", file_name)
            shutil.copyfileobj(response.response, f)
        else:
            raise ValueError("Don't know how to handle response type: {}".format(type(response.response)))


def _save_redirected_response_data(response, file_name):
    # type: (Response, str) -> None
    """Download the URL of a remote resource we got redirected to, and save it locally

    Return the local file name
    """
    resource_url = response.headers['Location']
    _log().debug("Resource is at %s, downloading ...", resource_url)
    with requests.get(resource_url, stream=True) as source, open(file_name, 'wb') as dest:
        source.raise_for_status()
        _log().debug("Resource downloading, HTTP status code is %d, Content-type is %s",
                     source.status_code,
                     source.headers.get('Content-type', 'unknown'))
        for chunk in source.iter_content(chunk_size=1024 * 16):
            dest.write(chunk)
    _log().debug("Remote resource downloaded to %s", file_name)


def get_resource_dataset(resource_obj):
    # type: (Resource) -> Tuple[Dict[str, Any], Dict[str, Any]]
    """Fetch the CKAN dataset dictionary for a DB-fetched resource
    """
    context = {"ignore_auth": True, "use_cache": False}
    dataset = toolkit.get_action('package_show')(context, {"id": resource_obj.package_id})
    resource = [r for r in dataset['resources'] if r['id'] == resource_obj.id][0]

    return dataset, resource


def get_unmigrated_resources():
    # type: () -> Generator[Resource, None, None]
    """Generator of un-migrated resource

    This works by fetching one resource at a time using SELECT FOR UPDATE SKIP LOCKED.
    Once the resource has been migrated to the new storage, it will be unlocked. This
    allows running multiple migrator scripts in parallel, without any conflicts and
    with small chance of re-doing any work.

    While a specific resource is being migrated, it will be locked for modification
    on the DB level. Users can still read the resource without any effect.
    """
    session = Session()
    session.revisioning_disabled = True

    # Start from inspecting all uploaded, undeleted resources
    all_resources = session.query(Resource).filter(
        Resource.url_type == 'upload',
        Resource.state != 'deleted',
    ).order_by(
        Resource.created
    ).options(load_only("id", "extras"))

    for resource in all_resources:
        if not _needs_migration(resource):
            _log().debug("Skipping resource %s as it was already migrated", resource.id)
            continue

        with db_transaction(session):
            locked_resource = session.query(Resource).filter(Resource.id == resource.id).\
                with_for_update(skip_locked=True).one_or_none()

            if locked_resource is None:
                _log().debug("Skipping resource %s as it is locked (being migrated?)", resource.id)
                continue

            # let's double check as the resource might have been migrated by another process by now
            if not _needs_migration(resource):
                continue

            yield resource


def _needs_migration(resource):
    # type: (Resource) -> bool
    """Check the attributes of a resource to see if it was migrated
    """
    if not (resource.extras.get('lfs_prefix') and resource.extras.get('sha256')):
        return True

    expected_prefix = '/'.join([helpers.storage_namespace(), resource.package_id])
    return resource.extras.get('lfs_prefix') != expected_prefix


@contextmanager
def db_transaction(session):
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    else:
        session.commit()


@contextmanager
def app_context():
    context = _get_auto_flask_context()
    try:
        context.push()
        yield context
    finally:
        context.pop()
