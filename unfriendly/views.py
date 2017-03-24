# -*- coding: utf-8 -*-
"""Django view handlers."""

from django.http import HttpResponseNotFound

try:
    from urllib.parse import unquote, urlparse
except ImportError:
    from urllib import unquote
    from urlparse import urlparse

try:
    from django.urls import Resolver404, resolve
except ImportError:
    from django.core.urlresolvers  import Resolver404, resolve

from unfriendly import settings
from unfriendly.utils import CheckSumError, InvalidKeyError, decrypt


def deobfuscate(request, key, juice=None):
    """
    Deobfuscates the URL and returns HttpResponse from source view.
    SEO juice is mostly ignored as it is intended for display purposes only.
    """
    try:
        url = decrypt(str(key),
                      settings.UNFRIENDLY_SECRET,
                      settings.UNFRIENDLY_IV,
                      checksum=settings.UNFRIENDLY_ENFORCE_CHECKSUM)
    except (CheckSumError, InvalidKeyError):
        return HttpResponseNotFound()

    try:
        url = url.decode('utf-8')
    except UnicodeDecodeError:
        return HttpResponseNotFound()

    url_parts = urlparse(unquote(url))
    path = url_parts.path
    query = url_parts.query

    try:
        view, args, kwargs = resolve(path)
    except Resolver404:
        return HttpResponseNotFound()

    # when using AsgiRequest its throwing error
    # Patch for it
    try:
        # fix-up the environ object
        environ = request.environ.copy()
        environ['PATH_INFO'] = path[len(environ['SCRIPT_NAME']):]
        environ['QUERY_STRING'] = query
    except:
        environ = request.message.copy()
        environ['query_string'] = query
        environ['path'] = path[len(environ['root_path']):]

    # init a new request
    patched_request = request.__class__(environ)

    # copy over any missing request attributes - this feels hackish
    missing_items = set(dir(request)) - set(dir(patched_request))
    while missing_items:
        missing_item = missing_items.pop()
        patched_request.__setattr__(missing_item,
                                    request.__getattribute__(missing_item))

    # mark this request as obfuscated
    patched_request.META['obfuscated'] = True

    response = view(patched_request, *args, **kwargs)

    # offer up a friendlier juice-powered filename if downloaded
    if juice and not response.has_header('Content-Disposition'):
        response['Content-Disposition'] = 'inline; filename=%s' % juice

    return response
