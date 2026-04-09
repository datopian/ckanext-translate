from google.cloud import translate_v3 as translate_v3
from google.oauth2 import service_account
import logging
import json
import re
import hashlib
import io
import html

import ckan.plugins.toolkit as tk
import ckanext.translate.logic.schema as schema
from ckan.common import config


log = logging.getLogger(__name__)


def _get_variables():
    translate_vars = {
        "project_id": config.get("ckanext.translate.google_project_id"),
        "location": config.get("ckanext.translate.google_location"),
        "service_account_file": config.get(
            "ckanext.translate.google_service_account_file"
        ),
    }

    if not all(translate_vars.values()):
        prettier_vars = json.dumps(translate_vars, indent=4)
        raise Exception(
            "Missing variables in config. Please add the following variables to your config:\n\n{vars}".format(
                vars=prettier_vars
            )
        )

    return translate_vars


def _get_client(service_account_file):
    credentials = service_account.Credentials.from_service_account_file(
        service_account_file
    )
    client = translate_v3.TranslationServiceClient(credentials=credentials)

    return client


def _ignore_terms(translate_values):
    ignore_list_path = config.get("ckanext.translate.ignore_list_path")
    terms = []

    if ignore_list_path:
        with io.open(ignore_list_path, "r", encoding="utf-8") as terms_file:
            terms = terms_file.read().splitlines()

    url_pattern = re.compile(r"https?://[a-zA-Z0-9\.\-\/\?\=\&\%\#\_]+")
    hash_to_original = {}
    translate_values = list(translate_values)

    for index, translate_value in enumerate(translate_values):
        # This was initially implemented as an attempt to fix the
        # `-` character being replaced with `-\n` in translated URLs.
        # It turns out, it's not required to solve that, but I'm
        # leaving it because it will prevent Google from accidentally
        # altering URLs. Even though the odds of that happening are low,
        # it's better to be safe than sorry).
        def _shield_url(url_match):
            original_url = url_match.group()
            url_hash = hashlib.sha256(original_url.encode("utf-8")).hexdigest()[:32]

            hash_to_original[url_hash] = original_url

            return url_hash

        translate_value = url_pattern.sub(_shield_url, translate_value)

        for term in terms:
            pattern = re.compile(re.escape(term), re.IGNORECASE | re.UNICODE)

            def _replace_with_hash(match):
                original_text = match.group()
                hash_value = hashlib.sha256(original_text.encode("utf-8")).hexdigest()[
                    :32
                ]

                if hash_value not in hash_to_original:
                    hash_to_original[hash_value] = original_text

                return hash_value

            translate_value = pattern.sub(_replace_with_hash, translate_value)

        translate_values[index] = translate_value

    return translate_values, hash_to_original


def translate(context, data_dict):
    translate_vars = _get_variables()
    client = _get_client(translate_vars["service_account_file"])
    project_id = translate_vars["project_id"]
    parent = client.location_path(project_id, translate_vars["location"])

    tk.check_access("translate", context, data_dict)

    data, errors = tk.navl_validate(data_dict, schema.translate(), context)

    if errors:
        raise tk.ValidationError(errors)

    translate_keys, translate_values = list(zip(*list(data["input"].items())))
    translate_values, hash_to_original = _ignore_terms(translate_values)

    try:
        response = client.translate_text(
            contents=translate_values,
            source_language_code=data_dict["from"],
            target_language_code=data_dict["to"],
            parent=parent,
            mime_type="text/html",
        )

    except Exception as e:
        raise tk.ValidationError({"message": str(e)})

    translated_dict = {}

    for index, translated_item in enumerate(response.translations):
        for hash_value, original_text in list(hash_to_original.items()):
            pattern = re.compile(re.escape(hash_value))
            # After text leaves this extension, a `\n` is inserted
            # after the `-` in some cases. This happens before it
            # gets to ckanext-scheming or ckanext-fluent, so it's
            # likely some sort of validation/sanitization step in
            # CKAN core. Replacing `-` with `%2d` prevents this
            # from happening, and it's functionally equivalent in
            # URLs, so it shouldn't cause any issues.
            original_text = (
                original_text.replace("-", "%2d")
                if original_text.startswith("http")
                else original_text
            )
            translated_item.translated_text = pattern.sub(
                lambda _: original_text, translated_item.translated_text
            )
        translated_dict.update(
            {
                list(translate_keys)[index]: html.unescape(
                    translated_item.translated_text
                )
            }
        )

    return {"output": translated_dict}


def get_actions():
    return {
        "translate": translate,
    }
