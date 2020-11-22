from ckan import model, plugins
from ckan.lib import uploader
from ckan.plugins import toolkit as tk
from flask import send_file

from .interfaces import IResourceDownloadHandler


def get_context():
    """Get a default context dict
    """
    return {
        'model': model,
        'user': tk.c.user,
        'auth_user_obj': tk.c.userobj,
    }


def call_pre_download_handlers(resource, package):
    """Call all registered plugins pre-download callback
    """
    for plugin in plugins.PluginImplementations(IResourceDownloadHandler):
        if not hasattr(plugin, 'pre_resource_download'):
            continue
        new_resource = plugin.pre_resource_download(resource, package)
        if new_resource:
            resource = new_resource

    return resource


def call_download_handlers(resource, package, filename=None):
    """Call all registered plugins download handlers
    """
    for plugin in plugins.PluginImplementations(IResourceDownloadHandler):
        if not hasattr(plugin, 'resource_download'):
            continue
        response = plugin.resource_download(resource, package, filename)
        if response:
            return response

    return fallback_download_method(resource)


def download_handler(resource, _, filename=None):
    """Get the download URL from LFS server and redirect the user there
    """
    if resource.get('url_type') != 'upload' or not resource.get('lfs_prefix'):
        return None

    context = get_context()
    data_dict = {'resource': resource,
                 'filename': filename}
    resource_download_spec = tk.get_action('get_resource_download_spec')(context, data_dict)
    href = resource_download_spec.get('href')

    if href:
        return tk.redirect_to(href)
    else:
        return tk.abort(404, tk._('No download is available'))


def fallback_download_method(resource):
    """Fall back to the built in CKAN download method
    """
    if resource.get('url_type') == 'upload':
        upload = uploader.get_resource_uploader(resource)
        filepath = upload.get_path(resource[u'id'])
        return send_file(filepath)
    elif u'url' not in resource:
        return tk.abort(404, tk._('No download is available'))

    return tk.redirect_to(resource[u'url'])
