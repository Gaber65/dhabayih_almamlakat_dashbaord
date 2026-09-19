{
    "name": "Jabin Users",
    "version": "17.0.1.0.0",
    "category": "Services/Jabin",
    "summary": "Jabin ERP - User profiles, user types, and multi-address management",
    "description": """
Jabin Users
===========

User-management domain for the Jabin ERP platform.

Provides:
    * Extended res.users with Jabin business fields (user type, balance,
      status, phone, avatar, last login).
    * Multi-address model (res.users.address).
    * REST APIs under /api/v1/users and /api/v1/addresses.
    * Service layer keeping business logic out of controllers.

    User types: Admin, Customer, Manager, Employee, Driver.
    """,
    "author": "Jabin Engineering",
    "website": "https://github.com/Gaber65/Jabin",
    "license": "Other proprietary",
    "depends": ["base", "jabin_core"],
    "data": [
        "security/ir.model.access.csv",
        "data/jabin_users_data.xml",
        # "views/address_views.xml",
    ],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
}
