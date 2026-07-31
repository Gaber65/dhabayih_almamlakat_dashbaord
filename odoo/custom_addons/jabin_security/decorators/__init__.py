# -*- coding: utf-8 -*-
"""Decorators sub-package of ``jabin_security``.

Re-exports the HTTP-level auth / permission decorators so that downstream
modules can do::

    from odoo.addons.jabin_security import auth_required, permission_required
"""

from .auth_required import auth_required, auth_optional  # noqa: F401
from .permission_required import permission_required  # noqa: F401
