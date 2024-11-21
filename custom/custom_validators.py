from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_lowercase(value: str):
    if not value.islower():
        raise ValidationError(_("Value should be lowercase."))


# def validate_country_codes(value: str):
#     ls = value.split(",")
#     for code in ls:
#         if not (code.isupper() and len(code) == 2) or " " in code:
#             raise ValidationError(_("Invalid string. Example: 'US,UK'"))
