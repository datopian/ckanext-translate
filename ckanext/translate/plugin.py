import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import logging

from ckan.config.declaration import Declaration, Key
from ckanext.translate.logic import action, auth

log = logging.getLogger(__name__)


class TranslatePlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IConfigDeclaration)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IActions)

    # IConfigurer
    def update_config(self, config_):
        toolkit.add_template_directory(config_, "templates")
        toolkit.add_public_directory(config_, "public")
        toolkit.add_resource("assets", "translate")

    # IConfigDeclaration
    def declare_config_options(self, declaration: Declaration, key: Key):
        declaration.annotate("ckanext-translate settings")
        declaration.declare(key.ckanext.translate.google_service_account_file).set_validators(
            "not_empty unicode_safe"
        )
        declaration.declare(key.ckanext.translate.google_project_id).set_validators(
            "not_empty unicode_safe"
        )
        declaration.declare(key.ckanext.translate.google_location).set_validators(
            "not_empty unicode_safe"
        )
        declaration.declare(key.ckanext.translate.ignore_list_path).set_validators(
            "ignore_missing unicode_safe"
        )

    # IAuthFunctions
    def get_auth_functions(self):
        return auth.get_auth_functions()

    # IActions
    def get_actions(self):
        return action.get_actions()
