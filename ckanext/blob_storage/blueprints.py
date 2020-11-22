"""ckanext-blob-storage Flask blueprints
"""
from ckan.plugins import toolkit
from flask import Blueprint

from .download_handler import call_download_handlers, call_pre_download_handlers, get_context

blueprint = Blueprint(
    'blob_storage',
    __name__,
)


def download(id, resource_id, filename=None):
    """Download resource blueprint

    This calls all registered download handlers in order, until
    a response is returned to the user
    """
    context = get_context()

    try:
        resource = toolkit.get_action('resource_show')(context, {'id': resource_id})
        if id != resource['package_id']:
            return toolkit.abort(404, toolkit._('Resource not found belonging to package'))

        package = toolkit.get_action('package_show')(context, {'id': id})

        resource = call_pre_download_handlers(resource, package)
        return call_download_handlers(resource, package, filename)

    except toolkit.ObjectNotFound:
        return toolkit.abort(404, toolkit._('Resource not found'))
    except toolkit.NotAuthorized:
        return toolkit.abort(401, toolkit._('Not authorized to read resource {0}'.format(resource_id)))


blueprint.add_url_rule(u'/dataset/<id>/resource/<resource_id>/download', view_func=download)
blueprint.add_url_rule(u'/dataset/<id>/resource/<resource_id>/download/<filename>', view_func=download)
