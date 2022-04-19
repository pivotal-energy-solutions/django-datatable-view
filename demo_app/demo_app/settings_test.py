# -*- coding: utf-8 -*-

import warnings

from .settings import *


class DisableMigrations(object):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

# Handle system warning as log messages
warnings.simplefilter("once")

for handler in LOGGING.get("handlers", []):
    LOGGING["handlers"][handler]["level"] = "ERROR"
for logger in LOGGING.get("loggers", []):
    LOGGING["loggers"][logger]["level"] = "ERROR"

mysql_db = DATABASES["default"]
DEFAULT_DB = {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
if os.environ.get("DB_TYPE") == "mysql":
    print("Using MySQL Backend!")
    DEFAULT_DB = mysql_db

DATABASES = {
    "default": DEFAULT_DB,
}
