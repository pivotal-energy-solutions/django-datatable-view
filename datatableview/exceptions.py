# -*- coding: utf-8 -*-


class ColumnError(Exception):
    """Some kind of problem with a datatable column."""


class SkipRecord(Exception):
    """User-raised problem with a record during serialization."""
