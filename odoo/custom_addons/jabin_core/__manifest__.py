{
    "name": "Jabin Core",
    "version": "17.0.1.0.0",
    "category": "Services/Jabin",
    "summary": "Jabin ERP - Core foundation (constants, utils, mixins, helpers, validators)",
    "description": """
Jabin Core
==========

Foundation infrastructure for the Jabin ERP platform.

Provides:
    * Centralised constants / enums
    * Unified API response builder
    * Centralised exception mapper
    * Reusable logging utilities (INFO / WARNING / ERROR / AUDIT)
    * Reusable Odoo mixins (Timestamp, Audit, Active, SoftDelete)
    * Pure-Python helpers (JSON, Datetime, Pagination, Validation, String)
    * Validation structure (Email, Phone, Password, Price, Weight, UUID)

This module contains NO business logic.
    """,
    "author": "Jabin Engineering",
    "website": "https://github.com/Gaber65/Jabin",
    "license": "Other proprietary",
    "depends": ["base"],
    # jabin_core ships no data, no views, no security of its own.
    "data": [],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
}
