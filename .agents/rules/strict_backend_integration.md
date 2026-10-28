# Strict Backend Integration Rule (No Dummy / Mock Data)

**Priority**: CRITICAL MANDATORY CONSTRAINT
**Applicable Projects**:
1. `c:\Users\ahmed\StudioProjects\dhabayih_lmamlaka` (Flutter Mobile App)
2. `c:\Users\ahmed\StudioProjects\dhabayih_lmamlaka_react_cartoon` (React / Web App)
3. `e:\Projcets\odoo17` (Odoo Backend)

## Principle:
1. **Zero Dummy / Mockup Data**:
   - Never generate synthetic IDs (e.g. `product.id * 100 + 1`), fake prices, or mock items in UI code.
   - Never use placeholder/Unsplash images for products or options that exist in Odoo.
   - All categories, products, sizes, options, branches, and fulfillment types must be strictly connected to and fetched from the real Odoo Back-End API (`https://api.zbayhalmmlkh.network` / local Odoo).
2. **Real Product Lifecycle**:
   - Products displayed in the UI must have their real Odoo ID, real price from `jabin.product` or `jabin.product.size`, real image from `jabin.product/main_image`, real cutting options (`jabin.cutting.option`), packaging (`jabin.packaging`), and excluded parts (`jabin.excluded.part`).
   - Carcass divisions / portions:
     - Whole carcasses are in Category 5 ("ذبائح غنم وماعز").
     - Quarter and Half portions are real standalone products in Category 8 ("أجزاء وأنصاف ذبائح") (e.g., "ربع ذبيحة غنم طازج", "نصف ذبيحة غنم طازج", etc.).
   - Cart additions, checkout, and favorites must strictly use real Odoo product IDs and valid backend relationships.
3. **UI Cleanliness & Single Source of Truth**:
   - Do not duplicate location / fulfillment / branch pickers in multiple places on the same screen. The AppBar is the primary location/branch selector. The home feed must remain clean, uncluttered, and spacious.
