# -*- coding: utf-8 -*-
import inspect
import hashlib
import logging

from django.core.cache import caches
from django.conf import settings

log = logging.getLogger(__name__)


class cache_types(object):
    NONE = None
    DEFAULT = "default"
    SIMPLE = "simple"  # Stores queryset objects directly in cache
    PK_LIST = "pk_list"  # Stores queryset pks in cache for later expansion back to queryset


try:
    CACHE_BACKEND = settings.DATATABLEVIEW_CACHE_BACKEND
except AttributeError:
    CACHE_BACKEND = "default"

try:
    CACHE_PREFIX = settings.DATATABLEVIEW_CACHE_PREFIX
except AttributeError:
    CACHE_PREFIX = "datatableview_"

try:
    DEFAULT_CACHE_TYPE = settings.DATATABLEVIEW_DEFAULT_CACHE_TYPE
except AttributeError:
    DEFAULT_CACHE_TYPE = cache_types.SIMPLE

try:
    CACHE_KEY_HASH = settings.DATATABLEVIEW_CACHE_KEY_HASH
except AttributeError:
    CACHE_KEY_HASH = True

try:
    CACHE_KEY_HASH_LENGTH = settings.DATATABLEVIEW_CACHE_KEY_HASH_LENGTH
except AttributeError:
    CACHE_KEY_HASH_LENGTH = None

cache = caches[CACHE_BACKEND]

hash_slice = None
if CACHE_KEY_HASH:
    hash_slice = slice(None, CACHE_KEY_HASH_LENGTH)


def _hash_key_component(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[hash_slice]


def get_cache_key(datatable_class, view=None, user=None, **kwargs):
    """
    Returns a cache key unique to the current table, and (if available) the request user.

    The ``view`` argument should be the class reference itself, since it is easily obtainable
    in contexts where the instance is not available.
    """

    datatable_name = datatable_class.__name__
    if datatable_name.endswith("_Synthesized"):
        datatable_name = datatable_name[:-12]
    datatable_id = "%s.%s" % (datatable_class.__module__, datatable_name)
    if CACHE_KEY_HASH:
        datatable_id = _hash_key_component(datatable_id)

    cache_key = "datatable_%s" % (datatable_id,)

    if view:
        if not inspect.isclass(view):
            # Reduce view to its class
            view = view.__class__

        view_id = "%s.%s" % (view.__module__, view.__name__)
        if CACHE_KEY_HASH:
            view_id = _hash_key_component(view_id)
        cache_key += "__view_%s" % (view_id,)

    if user and user.is_authenticated:
        cache_key += "__user_%s" % (user.pk,)

    # All other kwargs are used directly to create a hashed suffix
    # Order the kwargs by key name, then convert them to their repr() values.
    items = sorted(kwargs.items(), key=lambda item: item[0])
    values = []
    for k, v in items:
        values.append("%r:%r" % (k, v))

    if values:
        kwargs_id = "__".join(values)
        kwargs_id = _hash_key_component(kwargs_id)
        cache_key += "__kwargs_%s" % (kwargs_id,)

    log.debug("Cache key derived for %r: %r (from kwargs %r)", datatable_class, cache_key, values)

    return cache_key


def get_cached_data(datatable, **kwargs):
    """Returns the cached object list under the appropriate key, or None if not set."""
    cache_key = "%s%s" % (CACHE_PREFIX, datatable.get_cache_key(**kwargs))
    data = cache.get(cache_key)
    log.debug("Reading data from cache at %r: %r", cache_key, data)
    return data


def cache_data(datatable, data, **kwargs):
    """Stores the object list in the cache under the appropriate key."""
    cache_key = "%s%s" % (CACHE_PREFIX, datatable.get_cache_key(**kwargs))
    log.debug("Setting data to cache at %r: %r", cache_key, data)
    cache.set(cache_key, data)
