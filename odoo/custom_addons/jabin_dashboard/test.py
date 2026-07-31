from pathlib import Path

PROJECT_NAME = "jabin_catalog"

FILES = [
    # Root
    "__init__.py",
    "__manifest__.py",

    # Models
    "models/__init__.py",
    "models/category.py",
    "models/product.py",
    "models/product_image.py",
    "models/cutting_option.py",
    "models/packaging.py",
    "models/excluded_part.py",

    # Services
    "services/__init__.py",
    "services/category_service.py",
    "services/product_service.py",
    "services/cutting_option_service.py",
    "services/packaging_service.py",
    "services/excluded_part_service.py",

    # Validators
    "validators/__init__.py",
    "validators/base_validator.py",
    "validators/category_validator.py",
    "validators/product_validator.py",

    # Controllers
    "controllers/__init__.py",
    "controllers/category_controller.py",
    "controllers/product_controller.py",
    "controllers/cutting_option_controller.py",
    "controllers/packaging_controller.py",
    "controllers/excluded_part_controller.py",

    # Views
    "views/category_views.xml",
    "views/product_views.xml",
    "views/cutting_option_views.xml",
    "views/packaging_views.xml",
    "views/excluded_part_views.xml",
    "views/menu_views.xml",

    # Security
    "security/ir.model.access.csv",
    "security/security_groups.xml",

    # Data
    "data/demo_data.xml",

    # Static
    "static/description/icon.png",

    # Localization
    "i18n/en.po",
]

ROOT = Path(PROJECT_NAME)

for file in FILES:
    path = ROOT / file
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        path.touch()

print("=" * 60)
print(f"✅ Project '{PROJECT_NAME}' created successfully!")
print(f"📂 Location : {ROOT.resolve()}")
print(f"📄 Total Files : {len(FILES)}")
print("=" * 60)

print("\nGenerated Structure:\n")

for p in sorted(ROOT.rglob("*")):
    indent = "    " * (len(p.relative_to(ROOT).parts) - 1)
    prefix = "📁" if p.is_dir() else "📄"
    print(f"{indent}{prefix} {p.name}")