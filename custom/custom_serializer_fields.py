from rest_framework import serializers

from custom.custom_validators import validate_lowercase


class EmailField(serializers.EmailField):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validators.append(validate_lowercase)
