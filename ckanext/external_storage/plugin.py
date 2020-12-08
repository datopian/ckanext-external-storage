import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit

from ckanext.authz_service.authzzie import Authzzie
from ckanext.authz_service.interfaces import IAuthorizationBindings

from . import actions, authz, helpers
from .blueprints import blueprint
from .download_handler import download_handler
from .interfaces import IResourceDownloadHandler


class ExternalStoragePlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IBlueprint)
    plugins.implements(plugins.IActions)
    plugins.implements(IAuthorizationBindings)
    plugins.implements(IResourceDownloadHandler, inherit=True)

    # IConfigurer

    def update_config(self, config):
        toolkit.add_template_directory(config, 'templates')
        toolkit.add_public_directory(config, 'public')
        toolkit.add_resource('fanstatic', 'external-storage')

    # ITemplateHelpers

    def get_helpers(self):
        return {'extstorage_server_url': helpers.server_url,
                'extstorage_resource_authz_scope': helpers.resource_authz_scope,
                'extstorage_resource_storage_prefix': helpers.resource_storage_prefix,
                'extstorage_organization_name': helpers.organization_name}

    # IBlueprint

    def get_blueprint(self):
        return blueprint

    # IActions

    def get_actions(self):
        return {
            'get_resource_download_spec': actions.get_resource_download_spec,
            'resource_schema_show': actions.resource_schema_show,
            'resource_sample_show': actions.resource_sample_show
        }

    # IAuthorizationBindings

    def register_authz_bindings(self, authorizer):
        # type: (Authzzie) -> None
        """Authorization Bindings

        This aliases CKANs Resource entity and actions to scopes understood by
        Giftless' JWT authorization scheme
        """
        authorizer.register_authorizer('res', authz.check_resource_permissions, actions={'read'})
        authorizer.register_type_alias('obj', 'res')
        authorizer.register_action_alias('write', 'update', 'res')
        authorizer.register_scope_normalizer('res', authz.normalize_object_scope)

    # IResourceDownloadHandler

    def resource_download(self, resource, package, filename=None):
        return download_handler(resource, package, filename)
