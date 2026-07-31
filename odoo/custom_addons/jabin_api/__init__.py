import odoo.http

_original_route = odoo.http.route

def _custom_route(route=None, **routing):
    if 'cors' not in routing:
        routing['cors'] = '*'
    return _original_route(route, **routing)

odoo.http.route = _custom_route

from . import controllers

