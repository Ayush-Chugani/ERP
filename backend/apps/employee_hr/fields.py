from django.db import models

class FixedCharField(models.CharField):
    def db_type(self, connection):
        return f"char({self.max_length})" if connection.vendor == "mysql" else super().db_type(connection)


class VarBinaryField(models.BinaryField):
    """Bound ciphertext storage to the source contract on MySQL."""
    def db_type(self, connection):
        return f"varbinary({self.max_length})" if connection.vendor == "mysql" else super().db_type(connection)
