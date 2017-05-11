import inspect
import hashlib

from django.core.cache import caches
from django.conf import settings


class cache_types(object):
    NONE = None
    SIMPLE = 'simple'  # Stores queryset objects directly in cache
    PK_LIST = 'pk_list'  # Stores queryset pks in cache for later expansion back to queryset


try:
    CACHE_BACKEND = settings.DATATABLEVIEW_CACHE_BACKEND
except AttributeError:
    CACHE_BACKEND = 'default'

try:
    CACHE_PREFIX = settings.DATATABLEVIEW_CACHE_PREFIX
except AttributeError:
    CACHE_PREFIX = 'datatableview_'

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
    return hashlib.sha1(s).hexdigest()[hash_slice]


def get_cache_key(datatable_class, view=None, user=None, **kwargs):
    """
    Returns a cache key unique to the current table, and (if available) the request user.

    The ``view`` argument should be the class reference itself, since it is easily obtainable
    in contexts where the instance is not available.
    """

    datatable_name = datatable_class.__name__
    if datatable_name.endswith('_Synthesized'):
        datatable_name = datatable_name[:-12]
    datatable_id = '%s.%s' % (datatable_class.__module__, datatable_name)
    if CACHE_KEY_HASH:
        datatable_id = _hash_key_component(datatable_id)

    cache_key = 'datatable_%s' % (datatable_id,)

    if view:
        if not inspect.isclass(view):
            # Try to get user information if 'user' param is missing
            if hasattr(view, 'request') and not user:
                user = view.request.user

            # Reduce view to its class
            view = view.__class__

        view_id = '%s.%s' % (view.__module__, view.__name__)
        if CACHE_KEY_HASH:
            view_id = _hash_key_component(view_id)
        cache_key += '__view_%s' % (view_id,)

    if user and user.is_authenticated():
        cache_key += '__user_%s' % (user.pk,)

    return cache_key


def get_cached_data(datatable_class, **kwargs):
    """ Returns the cached object list, or None if not set. """
    cache_key = '%s%s' % (CACHE_PREFIX, datatable_class.get_cache_key(**kwargs))
    return cache.get(cache_key)


def cache_data(datatable_class, data, **kwargs):
    cache_key = '%s%s' % (CACHE_PREFIX, datatable_class.get_cache_key(**kwargs))
    cache.set(cache_key, data)
