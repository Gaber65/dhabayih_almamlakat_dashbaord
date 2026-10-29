import base64
import json
import logging
import time
from typing import Dict, Any, Optional, List, Tuple

_logger = logging.getLogger(__name__)

from odoo import http, _
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.jabin_api.controllers import BaseApiController
from odoo.addons.jabin_core import ResponseBuilder
from odoo.addons.jabin_security.utils.token_auth import require_token
from odoo.addons.jabin_security.decorators.permission_required import permission_required

from ..services.product_service import ProductService
from ..validators.product_validator import ProductValidator


# Allowed image MIME types for upload
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


def _parse_request_data() -> Dict[str, Any]:
    """
    Parse request data from either multipart/form-data or JSON.

    Returns a dictionary of values ready for service layer consumption.
    """
    content_type = request.httprequest.content_type or ""
    vals = {}

    if "multipart/form-data" in content_type:
        # Pull scalar fields from form data
        vals = {
            k: v
            for k, v in request.httprequest.form.items()
            if k not in ["id"]
        }

        # Handle boolean fields
        for bool_field in ("active", "is_featured", "is_best_seller", "is_carcass"):
            if bool_field in vals:
                vals[bool_field] = vals[bool_field].lower() not in ("false", "0", "no")

        # Handle numeric fields
        for num_field in (
            "purchase_price", "selling_price", "discount_value",
            "stock_quantity", "minimum_stock", "weight", "preparation_time"
        ):
            if num_field in vals and vals[num_field]:
                try:
                    vals[num_field] = float(vals[num_field])
                except ValueError:
                    raise ValueError(f"Field '{num_field}' must be a valid number.")

        # Handle integer fields
        if "category_id" in vals and vals["category_id"]:
            try:
                vals["category_id"] = int(vals["category_id"])
            except ValueError:
                raise ValueError("Category ID must be a valid integer.")

    else:
        # Parse JSON body
        raw = request.httprequest.data
        if raw:
            try:
                vals = json.loads(raw)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON payload.")

        # Remove unwanted fields if present
        vals.pop("id", None)
        vals.pop("image_path", None)
        vals.pop("image_url", None)

    # Convert Many2Many lists to Odoo ORM command format [(6, 0, [ids])]
    for m2m_field in ("cutting_option_ids", "packaging_ids", "excluded_part_ids"):
        if m2m_field in vals:
            val = vals[m2m_field]
            if isinstance(val, list):
                clean_ids = []
                for item in val:
                    if isinstance(item, int):
                        clean_ids.append(item)
                    elif isinstance(item, str) and item.isdigit():
                        clean_ids.append(int(item))
                    elif isinstance(item, dict) and "id" in item:
                        clean_ids.append(int(item["id"]))
                vals[m2m_field] = [(6, 0, clean_ids)]

    # Handle base64 image in JSON
    if "main_image" in vals and isinstance(vals["main_image"], str):
        img_str = vals["main_image"].strip()
        if img_str.startswith("http://") or img_str.startswith("https://"):
            vals.pop("main_image", None)
        elif "," in img_str and "base64" in img_str:
            vals["main_image"] = img_str.split(",", 1)[1].strip()
        else:
            vals["main_image"] = img_str

    if "image" in vals and not vals.get("main_image"):
        img_str = str(vals.pop("image")).strip()
        if not (img_str.startswith("http://") or img_str.startswith("https://")):
            if "," in img_str and "base64" in img_str:
                vals["main_image"] = img_str.split(",", 1)[1].strip()
            else:
                vals["main_image"] = img_str

    # Preserve raw_sizes before stripping non-model fields
    if "sizes" in vals:
        vals["_raw_sizes"] = vals.pop("sizes")

    # Strip computed / non-model fields that would cause write errors
    for f in (
        "is_available", "is_on_offer", "offer_price", "profit",
        "offer_profit", "profit_percentage", "loyalty_points",
        "has_sizes", "cutting_options", "packaging_options",
        "excluded_parts", "images"
    ):
        vals.pop(f, None)

    # Map Flutter fields
    name = vals.pop("name_ar", None) or vals.pop("title", None) or vals.get("name") or vals.pop("name_en", None)
    if name:
        vals["name"] = " ".join(str(name).strip().split())
    vals.pop("name_ar", None)
    vals.pop("name_en", None)
    vals.pop("title", None)

    if "price" in vals and "selling_price" not in vals:
        vals["selling_price"] = vals.pop("price")
    vals.pop("price", None)

    if "selling_price" in vals and vals["selling_price"] is not None:
        try:
            vals["selling_price"] = float(vals["selling_price"])
        except ValueError:
            pass

    if "purchase_price" in vals and vals["purchase_price"] is not None:
        try:
            vals["purchase_price"] = float(vals["purchase_price"])
        except ValueError:
            pass
    elif "selling_price" in vals:
        vals["purchase_price"] = round(float(vals.get("selling_price", 0.0)) * 0.7, 2)

    if vals.get("sku"):
        vals["sku"] = str(vals["sku"]).strip().upper().replace(" ", "-")
    else:
        vals["sku"] = f"PROD-{int(time.time() * 1000)}"

    if "category_id" in vals:
        if not vals["category_id"] or vals["category_id"] == 0:
            vals.pop("category_id", None)
        else:
            try:
                vals["category_id"] = int(vals["category_id"])
            except ValueError:
                vals.pop("category_id", None)

    return vals


def _read_single_image(file_field_name: str) -> Optional[str]:
    """
    Read one uploaded image from multipart/form-data.

    Returns base64-encoded string for an Odoo Binary field, or None.
    Raises ValueError on unsupported type or empty file.
    """
    uploaded = request.httprequest.files.get(file_field_name)
    if not uploaded:
        return None

    content_type = (uploaded.content_type or "").lower().split(";")[0].strip()
    ProductValidator.validate_image_type(content_type)

    raw = uploaded.read()
    if not raw:
        raise ValueError(f"Uploaded file '{file_field_name}' is empty.")

    return base64.b64encode(raw).decode('utf-8')


def _read_multiple_images(file_field_name: str = "images") -> List[str]:
    """
    Read multiple uploaded images from multipart/form-data.

    Returns a list of base64-encoded strings (may be empty).
    Raises ValueError on any unsupported type or empty file.
    """
    files = request.httprequest.files.getlist(file_field_name)
    results = []

    for uploaded in files:
        content_type = (uploaded.content_type or "").lower().split(";")[0].strip()
        ProductValidator.validate_image_type(content_type)

        raw = uploaded.read()
        if not raw:
            raise ValueError("One of the uploaded image files is empty.")

        results.append(base64.b64encode(raw).decode('utf-8'))

    return results


def _get_lang() -> str:
    """Get language from query param or Accept-Language header."""
    lang_param = (request.params.get("lang") if hasattr(request, "params") else None) or request.httprequest.args.get("lang")
    if lang_param:
        lp = lang_param.strip().lower()
        if lp.startswith("ar"):
            return "ar_001"
        elif lp.startswith("en"):
            return "en_US"

    accept_lang = request.httprequest.headers.get("Accept-Language", "")
    if accept_lang:
        for part in accept_lang.split(","):
            part_lang = part.split(";")[0].strip().lower()
            if part_lang.startswith("ar"):
                return "ar_001"
            elif part_lang.startswith("en"):
                return "en_US"

    return "ar_001"


def _extract_multilang(record, field_name: str) -> Tuple[str, str]:
    """Extract (val_ar, val_en) safely from a translatable field."""
    raw = None
    try:
        data = record.read([field_name])[0]
        raw = data.get(field_name)
    except Exception:
        pass

    val_ar = ""
    val_en = ""
    if isinstance(raw, dict):
        val_ar = raw.get("ar_001") or raw.get("ar") or ""
        val_en = raw.get("en_US") or raw.get("en") or ""

    if not val_ar and val_en:
        if any('\u0600' <= c <= '\u06FF' for c in val_en):
            val_ar = val_en
            val_en = ""
    elif not val_en and val_ar:
        if not any('\u0600' <= c <= '\u06FF' for c in val_ar):
            val_en = val_ar
            val_ar = ""

    fallback = getattr(record, field_name, "") or ""
    if not val_ar and fallback:
        val_ar = fallback
    if not val_en and fallback:
        val_en = fallback

    return str(val_ar or ""), str(val_en or "")


def _get_product_main_image_url(product) -> Optional[str]:
    """Get the primary image URL for a product with cache-busting version query."""
    v = int(product.write_date.timestamp()) if getattr(product, "write_date", False) else 1
    if getattr(product, "main_image", False):
        url = BaseApiController.build_image_url("jabin.product", product.id, "main_image")
        return f"{url}?v={v}" if url else None
    first_img = product.product_image_ids[:1]
    if first_img:
        v_img = int(first_img.write_date.timestamp()) if getattr(first_img, "write_date", False) else v
        url = BaseApiController.build_image_url("jabin.product.image", first_img.id, "image")
        return f"{url}?v={v_img}" if url else None
    return None


def _serialize_product(product) -> Dict[str, Any]:
    """Return the full product dict used by get_product."""
    main_img_url = _get_product_main_image_url(product)
    name_ar, name_en = _extract_multilang(product, "name")
    desc_ar, desc_en = _extract_multilang(product, "description")
    current_lang = _get_lang()
    active_name = name_en if current_lang == "en_US" and name_en else (name_ar or name_en)
    active_desc = desc_en if current_lang == "en_US" and desc_en else (desc_ar or desc_en)

    is_on_offer = bool(product.is_on_offer or (product.offer_price and product.selling_price and product.offer_price < product.selling_price))
    d_type = product.discount_type or "percentage"
    d_val = float(product.discount_value or 0.0)
    selling = float(product.selling_price or 0.0)
    offer_pr = float(product.offer_price or 0.0)

    active_sizes = (
        product.size_ids.filtered(lambda x: x.active).sorted(key=lambda x: (x.sequence, x.id))
        if hasattr(product, "size_ids")
        else []
    )
    full_sizes = [s for s in active_sizes if (getattr(s, "portion_type", "full") or "full") == "full"]
    half_sizes = [s for s in active_sizes if getattr(s, "portion_type", "full") == "half"]
    quarter_sizes = [s for s in active_sizes if getattr(s, "portion_type", "full") == "quarter"]

    portions_list = []
    if getattr(product, "is_carcass", False) and active_sizes:
        if full_sizes:
            portions_list.append({
                "type": "full",
                "name": "كامل",
                "title": f"{product.name} كامل",
                "subtitle": "ذبيحة كاملة مجهزة بالكامل",
                "image_url": main_img_url,
                "starting_price": min(s.price for s in full_sizes),
                "size_count": len(full_sizes),
            })
        if half_sizes:
            portions_list.append({
                "type": "half",
                "name": "نصف",
                "title": f"نصف {product.name}",
                "subtitle": "نصف ذبيحة طازج مقسوم بالطول",
                "image_url": BaseApiController.build_image_url("jabin.product", product.id, "half_image", bool(getattr(product, 'half_image', False))) or main_img_url,
                "starting_price": min(s.price for s in half_sizes),
                "size_count": len(half_sizes),
            })
        if quarter_sizes:
            portions_list.append({
                "type": "quarter",
                "name": "ربع",
                "title": f"ربع {product.name}",
                "subtitle": "ربع متكامل (كتف أو فخذ مع ضلوع)",
                "image_url": BaseApiController.build_image_url("jabin.product", product.id, "quarter_image", bool(getattr(product, 'quarter_image', False))) or main_img_url,
                "starting_price": min(s.price for s in quarter_sizes),
                "size_count": len(quarter_sizes),
            })

    return {
        "id": product.id,
        "category_id": product.category_id.id,
        "category_name": product.category_id.name,
        "name": active_name,
        "name_ar": name_ar,
        "name_en": name_en,
        "description": active_desc,
        "description_ar": desc_ar,
        "description_en": desc_en,
        "sku": product.sku or "",
        "barcode": product.barcode or "",
        "purchase_price": product.purchase_price,
        "selling_price": product.selling_price,
        "discount_type": d_type,
        "discount_value": d_val,
        "offer_price": product.offer_price,
        "offer_start_date": str(product.offer_start_date) if product.offer_start_date else None,
        "offer_end_date": str(product.offer_end_date) if product.offer_end_date else None,
        "is_on_offer": is_on_offer,
        "profit": product.profit,
        "offer_profit": product.offer_profit,
        "profit_percentage": product.profit_percentage,
        "stock_quantity": product.stock_quantity,
        "minimum_stock": product.minimum_stock,
        "weight": product.weight,
        "preparation_time": product.preparation_time,
        "main_image": main_img_url,
        "main_image_url": main_img_url,
        "image_url": main_img_url,
        "active": product.active,
        "is_available": product.is_available,
        "is_featured": product.is_featured,
        "is_best_seller": product.is_best_seller,
        "is_offer": is_on_offer,
        "is_carcass": bool(getattr(product, "is_carcass", False)),
        "has_sizes": bool(active_sizes),
        "sizes": [
            {
                "id": s.id,
                "name": s.name,
                "sub_title": s.sub_title or "",
                "portion_type": getattr(s, "portion_type", "full") or "full",
                "weight_range": getattr(s, "weight_range", "") or "",
                "min_weight": getattr(s, "min_weight", 0.0) or 0.0,
                "max_weight": getattr(s, "max_weight", 0.0) or 0.0,
                "price": round(s.price * (1 - d_val / 100), 2) if is_on_offer and d_type == "percentage" and d_val > 0 else (round(s.price * (offer_pr / selling), 2) if is_on_offer and offer_pr > 0 and selling > 0 and offer_pr < selling else s.price),
                "original_price": s.price if is_on_offer else None,
                "offer_price": round(s.price * (1 - d_val / 100), 2) if is_on_offer and d_type == "percentage" and d_val > 0 else (round(s.price * (offer_pr / selling), 2) if is_on_offer and offer_pr > 0 and selling > 0 and offer_pr < selling else None),
                "calories": s.calories,
                "loyalty_points": s.loyalty_points,
                "points_price": s.points_price,
                "is_default": s.is_default,
                "sequence": s.sequence,
                "active": s.active,
                "is_active": s.active,
            }
            for s in active_sizes
        ],
        "portions": portions_list,
        "cutting_options": [
            {
                "id": opt.id,
                "name": opt.name,
                "extra_price": float(getattr(opt, "extra_price", 0.0) or 0.0),
            }
            for opt in product.cutting_option_ids.filtered(lambda x: x.active)
        ],
        "packaging_options": [
            {
                "id": pkg.id,
                "name": pkg.name,
                "extra_price": float(getattr(pkg, "extra_price", 0.0) or 0.0),
            }
            for pkg in product.packaging_ids.filtered(lambda x: x.active)
        ],
        "excluded_parts": [
            {
                "id": part.id,
                "name": part.name,
                "extra_price": 0.0,
            }
            for part in product.excluded_part_ids.filtered(lambda x: x.active)
        ],
        "images": [
            {
                "id": img.id,
                "sequence": img.sequence,
                "image": BaseApiController.build_image_url("jabin.product.image", img.id, "image", bool(img.image)),
                "image_url": BaseApiController.build_image_url("jabin.product.image", img.id, "image", bool(img.image)),
            }
            for img in product.product_image_ids
        ],
    }


class ProductController(BaseApiController):
    """Product REST API Controller following Category module standards."""

    # ------------------------------------------------------------------
    # POST /api/catalog/product/create
    # Accepts: application/json OR multipart/form-data
    # ------------------------------------------------------------------
    @http.route(
        ["/api/v1/products", "/api/catalog/product/create"],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    @permission_required("products.manage")
    def create_product(self, **kwargs):
        """Create a new product."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            try:
                # Parse request data
                vals = _parse_request_data()

                # Handle images from multipart/form-data
                content_type = request.httprequest.content_type or ""
                if "multipart/form-data" in content_type:
                    # Single main image
                    main_image_data = _read_single_image("main_image")
                    if main_image_data is not None:
                        vals["main_image"] = main_image_data

                    # Multiple additional images
                    extra_images = _read_multiple_images("images")
                    if extra_images:
                        vals["product_image_ids"] = [
                            (0, 0, {"image": img_b64, "sequence": idx * 10})
                            for idx, img_b64 in enumerate(extra_images)
                        ]

                # Ensure category_id is set
                if not vals.get("category_id"):
                    first_cat = request.env['jabin.category'].sudo().search([('active', '=', True)], limit=1)
                    if first_cat:
                        vals["category_id"] = first_cat.id

                raw_sizes = vals.pop("_raw_sizes", None)
                if raw_sizes is None:
                    raw_sizes = vals.pop("sizes", None)

                # Create product via service
                product = ProductService.create(
                    request.env,
                    vals,
                )

                # Save custom carcass sizes ONLY if explicitly provided in raw_sizes
                if raw_sizes and isinstance(raw_sizes, list):
                    for idx, s in enumerate(raw_sizes):
                        if isinstance(s, dict) and s.get("name") and s.get("price") is not None:
                            try:
                                request.env["jabin.product.size"].sudo().create({
                                    "product_id": product.id,
                                    "name": str(s.get("name")).strip(),
                                    "sub_title": str(s.get("sub_title") or "").strip(),
                                    "price": float(s.get("price", 0.0)),
                                    "calories": int(s.get("calories") or 243),
                                    "sequence": int(s.get("sequence") or ((idx + 1) * 10)),
                                    "portion_type": str(s.get("portion_type") or "full").lower().strip(),
                                    "weight_range": str(s.get("weight_range") or "").strip(),
                                    "is_default": bool(s.get("is_default", idx == 0)),
                                    "active": bool(s.get("active", True) if "active" in s else s.get("is_active", True)),
                                })
                            except Exception as size_err:
                                _logger.warning("Failed to save size on create: %s", size_err)
                product.invalidate_recordset()
                active_sizes = product.with_context(active_test=False).size_ids.filtered(lambda x: x.active)
                product.sudo().write({"has_sizes": bool(active_sizes)})

                # Build success response
                ctx.set_body(
                    ResponseBuilder.success(
                        data=_serialize_product(product),
                        message=_("Product created successfully"),
                        code=201,
                    )
                )
            except ValidationError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=400
                    )
                )
            except ValueError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=400
                    )
                )
            except Exception as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=_("An error occurred while creating the product: %s") % str(e),
                        code=500
                    )
                )

        return ctx.response

    # ------------------------------------------------------------------
    # GET /api/catalog/product/<id>
    # ------------------------------------------------------------------
    @http.route(
        ["/api/v1/products/<int:product_id>", "/api/catalog/product/<int:product_id>"],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def get_product(self, product_id, **kwargs):
        """Get a single product by ID."""
        with self.handle() as ctx:
            try:
                # Get language from header
                lang = _get_lang()

                # Get product via service
                product = ProductService.get_by_id(
                    request.env,
                    product_id,
                    lang=lang
                )

                # Build response data
                ctx.set_body(
                    ResponseBuilder.success(
                        data=_serialize_product(product),
                        message=_("Product retrieved successfully"),
                    )
                )
            except ValidationError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=404
                    )
                )
            except Exception as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=_("An error occurred while retrieving the product: %s") % str(e),
                        code=500
                    )
                )

        return ctx.response

    # ------------------------------------------------------------------
    # GET /api/catalog/products
    # ------------------------------------------------------------------
    @http.route(
        ["/api/v1/products", "/api/catalog/products"],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        cors="*",
    )
    def get_products(self, **kwargs):
        """Get paginated list of products."""
        with self.handle() as ctx:
            try:
                # Parse and validate parameters
                try:
                    limit = int(kwargs.get("limit", 100))
                    offset = int(kwargs.get("offset", 0))
                except ValueError:
                    raise ValueError("Limit and offset must be valid integers.")

                if limit < 1 or limit > 1000:
                    raise ValueError("Limit must be between 1 and 1000.")
                if offset < 0:
                    raise ValueError("Offset must be at least 0.")

                # Build domain
                domain = []

                search_query = kwargs.get("search") or kwargs.get("query")
                if search_query:
                    domain.append("|")
                    domain.append(("name", "ilike", search_query))
                    domain.append(("sku", "ilike", search_query))

                # Generic filter param helper
                filter_param = kwargs.get("filter")
                if filter_param == "best_seller":
                    domain.append(("is_best_seller", "=", True))
                elif filter_param == "featured":
                    domain.append(("is_featured", "=", True))
                elif filter_param in ("offers", "on_offer"):
                    domain.append(("is_on_offer", "=", True))
                elif filter_param == "active":
                    domain.append(("active", "=", True))
                elif filter_param == "inactive":
                    domain.append(("active", "=", False))
                elif filter_param == "low_stock":
                    domain.append(("stock_quantity", "<=", 5))

                if kwargs.get("category_id"):
                    try:
                        domain.append(("category_id", "=", int(kwargs["category_id"])))
                    except ValueError:
                        raise ValueError("Category ID must be a valid integer.")

                if kwargs.get("active"):
                    active = kwargs["active"]
                    if active.lower() in ("true", "1", "yes"):
                        domain.append(("active", "=", True))
                    elif active.lower() in ("false", "0", "no"):
                        domain.append(("active", "=", False))

                if kwargs.get("on_offer"):
                    on_offer = kwargs["on_offer"]
                    if on_offer.lower() in ("true", "1", "yes"):
                        domain.append(("is_on_offer", "=", True))
                    elif on_offer.lower() in ("false", "0", "no"):
                        domain.append(("is_on_offer", "=", False))

                if kwargs.get("is_featured"):
                    featured = kwargs["is_featured"]
                    if featured.lower() in ("true", "1", "yes"):
                        domain.append(("is_featured", "=", True))
                    elif featured.lower() in ("false", "0", "no"):
                        domain.append(("is_featured", "=", False))

                if kwargs.get("is_best_seller"):
                    best_seller = kwargs["is_best_seller"]
                    if best_seller.lower() in ("true", "1", "yes"):
                        domain.append(("is_best_seller", "=", True))
                    elif best_seller.lower() in ("false", "0", "no"):
                        domain.append(("is_best_seller", "=", False))

                # Get language from header
                lang = _get_lang()

                # Get products via service
                records, total = ProductService.get_list(
                    request.env,
                    domain=domain,
                    limit=limit,
                    offset=offset,
                    order="name",
                    lang=lang
                )

                # Build response data
                response_data = {
                    "data": [_serialize_product(p) for p in records],
                    "pagination": {
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                    }
                }

                ctx.set_body(
                    ResponseBuilder.success(
                        data=response_data,
                        message=_("Products retrieved successfully"),
                    )
                )
            except ValidationError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=400
                    )
                )
            except ValueError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=400
                    )
                )
            except Exception as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=_("An error occurred while retrieving products: %s") % str(e),
                        code=500
                    )
                )

        return ctx.response

    # ------------------------------------------------------------------
    # PUT /api/catalog/product/<id>
    # Accepts: application/json OR multipart/form-data
    # ------------------------------------------------------------------
    @http.route(
        ["/api/v1/products/<int:product_id>", "/api/catalog/product/<int:product_id>"],
        type="http",
        auth="public",
        methods=["PUT"],
        csrf=False,
        cors="*",
    )
    @permission_required("products.manage")
    def update_product(self, product_id, **kwargs):
        """Update an existing product."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            try:
                # Parse request data
                vals = _parse_request_data()

                # Handle images from multipart/form-data
                content_type = request.httprequest.content_type or ""
                if "multipart/form-data" in content_type:
                    # Single main image
                    main_image_data = _read_single_image("main_image")
                    if main_image_data is not None:
                        vals["main_image"] = main_image_data

                    # Multiple additional images (append to existing)
                    extra_images = _read_multiple_images("images")
                    if extra_images:
                        # Get existing images to determine sequence
                        product = ProductService.get_by_id(
                            request.env, product_id
                        )
                        existing_count = len(product.product_image_ids)
                        start_sequence = existing_count * 10
                        vals["product_image_ids"] = [
                            (0, 0, {"image": img_b64, "sequence": start_sequence + idx * 10})
                            for idx, img_b64 in enumerate(extra_images)
                        ]

                raw_sizes = vals.pop("_raw_sizes", None)
                if raw_sizes is None:
                    raw_sizes = vals.pop("sizes", None)

                # Update product via service
                product = ProductService.update(
                    request.env,
                    product_id,
                    vals,
                )

                # Synchronize custom carcass sizes when provided (dashboard is source of truth)
                if raw_sizes is not None and isinstance(raw_sizes, list):
                    SizeModel = request.env["jabin.product.size"].sudo().with_context(active_test=False)
                    kept_size_ids = set()
                    for idx, s in enumerate(raw_sizes):
                        if not isinstance(s, dict) or not s.get("name"):
                            continue
                        size_id = s.get("id")
                        size_vals = {
                            "name": str(s.get("name")).strip(),
                            "sub_title": str(s.get("sub_title") or "").strip(),
                            "price": float(s.get("price", 0.0)),
                            "calories": int(s.get("calories") or 243),
                            "sequence": int(s.get("sequence") or ((idx + 1) * 10)),
                            "portion_type": str(s.get("portion_type") or "full").lower().strip(),
                            "weight_range": str(s.get("weight_range") or "").strip(),
                            "is_default": bool(s.get("is_default", False)),
                            "active": bool(s.get("active", True) if "active" in s else s.get("is_active", True)),
                        }
                        if s.get("min_weight") is not None:
                            try:
                                size_vals["min_weight"] = float(s["min_weight"])
                            except (ValueError, TypeError):
                                pass
                        if s.get("max_weight") is not None:
                            try:
                                size_vals["max_weight"] = float(s["max_weight"])
                            except (ValueError, TypeError):
                                pass
                        try:
                            if size_id:
                                existing = SizeModel.browse(int(size_id))
                                if existing.exists() and existing.product_id.id == product.id:
                                    existing.write(size_vals)
                                    kept_size_ids.add(existing.id)
                                    continue
                            size_vals["product_id"] = product.id
                            created_size = SizeModel.create(size_vals)
                            kept_size_ids.add(created_size.id)
                        except Exception as size_err:
                            _logger.warning("Failed to save size on update: %s", size_err)

                    # Remove or deactivate sizes that were removed in the dashboard
                    existing_all = SizeModel.search([("product_id", "=", product.id)])
                    for old_size in existing_all:
                        if old_size.id not in kept_size_ids:
                            try:
                                old_size.unlink()
                            except Exception:
                                old_size.write({"active": False})

                    product.invalidate_recordset()
                    active_sizes = SizeModel.search([("product_id", "=", product.id), ("active", "=", True)])
                    product.sudo().write({"has_sizes": bool(active_sizes)})

                product.invalidate_recordset()
                # Build success response
                ctx.set_body(
                    ResponseBuilder.success(
                        data=_serialize_product(product),
                        message=_("Product updated successfully"),
                    )
                )
            except ValidationError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=400
                    )
                )
            except ValueError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=400
                    )
                )
            except Exception as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=_("An error occurred while updating the product: %s") % str(e),
                        code=500
                    )
                )

        return ctx.response

    # ------------------------------------------------------------------
    # DELETE /api/catalog/product/<id>
    # ------------------------------------------------------------------
    @http.route(
        ["/api/v1/products/<int:product_id>", "/api/catalog/product/<int:product_id>"],
        type="http",
        auth="public",
        methods=["DELETE"],
        csrf=False,
        cors="*",
    )
    @permission_required("products.manage")
    def delete_product(self, product_id, **kwargs):
        """Delete a product."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            try:
                # Delete product via service
                ProductService.delete(
                    request.env,
                    product_id,
                )

                # Build success response
                ctx.set_body(
                    ResponseBuilder.success(
                        message=_("Product deleted successfully"),
                    )
                )
            except ValidationError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=400
                    )
                )
            except Exception as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=_("An error occurred while deleting the product: %s") % str(e),
                        code=500
                    )
                )

        return ctx.response

    # ------------------------------------------------------------------
    # POST /api/catalog/product/<id>/stock
    # ------------------------------------------------------------------
    @http.route(
        ["/api/v1/products/<int:product_id>/stock", "/api/catalog/product/<int:product_id>/stock"],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    @permission_required("products.manage")
    def update_stock(self, product_id, **kwargs):
        """Update product stock."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            try:
                # Parse request data
                raw = request.httprequest.data
                data = json.loads(raw) if raw else {}

                if "quantity" not in data:
                    raise ValueError("Quantity is required.")

                try:
                    quantity = float(data["quantity"])
                except ValueError:
                    raise ValueError("Quantity must be a valid number.")

                # Update stock via service
                product = ProductService.update_stock(
                    request.env,
                    product_id,
                    quantity,
                )

                # Build success response
                ctx.set_body(
                    ResponseBuilder.success(
                        data={
                            "id": product.id,
                            "name": product.name,
                            "stock_quantity": product.stock_quantity,
                            "is_available": product.is_available,
                        },
                        message=_("Stock updated by %(quantity)s units") % {
                            'quantity': quantity
                        },
                    )
                )
            except ValidationError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=400
                    )
                )
            except ValueError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=400
                    )
                )
            except Exception as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=_("An error occurred while updating stock: %s") % str(e),
                        code=500
                    )
                )

        return ctx.response

    # ------------------------------------------------------------------
    # POST /api/catalog/product/<id>/toggle-active
    # ------------------------------------------------------------------
    @http.route(
        ["/api/v1/products/<int:product_id>/toggle-active", "/api/catalog/product/<int:product_id>/toggle-active"],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        cors="*",
    )
    @permission_required("products.manage")
    def toggle_active(self, product_id, **kwargs):
        """Toggle product active status."""
        # Require authentication for data modification
        denied = require_token()
        if denied:
            return denied

        with self.handle() as ctx:
            try:
                # Toggle active via service
                product = ProductService.toggle_active(
                    request.env,
                    product_id,
                )

                # Build success response
                ctx.set_body(
                    ResponseBuilder.success(
                        data={
                            "id": product.id,
                            "name": product.name,
                            "active": product.active,
                        },
                        message=_("Product status toggled successfully"),
                    )
                )
            except ValidationError as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=str(e),
                        code=400
                    )
                )
            except Exception as e:
                ctx.set_body(
                    ResponseBuilder.error(
                        message=_("An error occurred while toggling product status: %s") % str(e),
                        code=500
                    )
                )

        return ctx.response