"""CKAN plugin interface
"""
from typing import Any, Dict, Optional

from ckan.plugins import Interface


class IResourceDownloadHandler(Interface):
    """A CKAN plugin interface for registering resource download handler plugins
    """

    def pre_resource_download(self, resource, package):
        # type: (Dict[str, Any], Dict[str, Any], Optional[str]) -> Optional[Dict[str, Any]]
        """Pre-resource download function

        Called before resource download handlers are called, accepting the
        resource and package as dict. Can be used to perform special
        authorization checks or somehow modify the resource data before
        other download handlers are called.

        Should either return a new / modified ``resource`` dictionary, or
        ``None`` in which case the original ``resource`` will remain in use.

        It can also raise exceptions, such as
        :exc:`ckan.plugins.toolkit.NotAuthorized` to abort the download process
        with a specific error.
        """
        pass

    def resource_download(self, resource, package, filename=None):
        # type: (Dict[str, Any], Dict[str, Any], Optional[str]) -> Any
        """Download a resource

        Called to download a resource, with the resource, package and filename
        (if specified in the download request URL) already provided, and after
        some basic authorization checks such as ``resource_show`` have been
        performed.

        All resource download handlers will be called in plugin load order by
        the Blueprint view function responsible for file downloads. The first
        plugin to return a non-empty value will stop the loop, and the value
        (assumed to be a response object) will be returned from the view
        function.

        This can be a response containing the resource data or a redirection
        response or even an error response.

        Download handlers can also raise exceptions such as
        :exc:`ckan.plugins.toolkit.ObjectNotFound` to break the cycle and
        return to the user with an error.

        Returning ``None`` or any other empty value will cause the next handler
        to be called.

        Eventually, if all registered handlers have been called and no response
        has been provided (and no exception has been raised), the default CKAN
        download behavior will be executed.
        """
        pass
