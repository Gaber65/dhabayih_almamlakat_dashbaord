from datetime import datetime, timedelta, timezone
from odoo import _
from odoo.exceptions import ValidationError


RIYADH_TZ = timezone(timedelta(hours=3))


def _validate_slaughter_schedule(slaughter_date_raw, slaughter_time_raw):
    """
    Validate slaughter date and time slot against Asia/Riyadh (UTC+3) business timezone.
    Returns (parsed_date, cleaned_time_str).
    """
    now_riyadh = datetime.now(RIYADH_TZ)
    today_riyadh = now_riyadh.date()

    if not slaughter_date_raw or not str(slaughter_date_raw).strip():
        if now_riyadh.hour >= 20:
            parsed_date = today_riyadh + timedelta(days=1)
        else:
            parsed_date = today_riyadh
    else:
        date_str = str(slaughter_date_raw).strip()[:10]
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            parsed_date = today_riyadh

    if parsed_date < today_riyadh:
        # Client submitted a past or yesterday date (due to client timezone offset or earlier opened session)
        # Safely advance to today's schedule
        parsed_date = today_riyadh

    if not slaughter_time_raw or not str(slaughter_time_raw).strip():
        time_str = "خلال 2 - 4 ساعات"
    else:
        time_str = str(slaughter_time_raw).strip()

    if parsed_date == today_riyadh:
        current_hour = now_riyadh.hour
        # If order is placed at night after 20:00 (8 PM) or before 06:00 (6 AM) for today, auto-adjust to morning slot
        if current_hour >= 20:
            parsed_date = today_riyadh + timedelta(days=1)
            time_str = "فترة الصباح (08:00 ص - 12:00 م)"
        elif current_hour < 8 and ("2 - 4" in time_str or "1 - 2" in time_str):
            time_str = "فترة الصباح (08:00 ص - 12:00 م)"
        elif ("صباح" in time_str or "08:00" in time_str or "8:00" in time_str) and current_hour >= 12:
            time_str = "فترة الظهر (12:00 م - 04:00 م)"
        elif ("ظهر" in time_str or "عصر" in time_str or "12:00" in time_str) and "مساء" not in time_str and current_hour >= 16:
            time_str = "فترة المساء (04:00 م - 08:00 م)"

    return parsed_date, time_str


class CheckoutService:
    """Service handling Cart to Order Checkout conversions."""

    @classmethod
    def process_checkout(
        cls,
        env,
        customer_id: int,
        delivery_type: str,
        address_id: int = None,
        branch_id: int = None,
        payment_method_id: int = None,
        notes: str = None,
        coupon_code: str = None,
        redeem_points=None,
        slaughter_date: str = None,
        slaughter_time: str = None,
    ):
        user = env["res.users"].sudo().browse(customer_id)
        if not user.exists():
            raise ValidationError(_("User not found."))

        # Cancel any previous abandoned pending_payment orders for this customer so points and cart are restored first
        try:
            old_unpaid_orders = env["jabin.order"].sudo().search([
                ("customer_id", "=", customer_id),
                ("state", "=", "pending_payment"),
                ("payment_status", "in", ("pending", "failed")),
            ])
            for old_ord in old_unpaid_orders:
                try:
                    env["jabin.customer.service"].sudo().trigger_status_transition(
                        old_ord.id, "cancelled", description="Cancelled automatically on new checkout attempt."
                    )
                except Exception:
                    old_ord.sudo().write({"state": "cancelled", "payment_status": "cancelled"})
        except Exception:
            pass

        parsed_slaughter_date, cleaned_slaughter_time = _validate_slaughter_schedule(
            slaughter_date, slaughter_time
        )

        cart = env["jabin.cart"].sudo().search([("customer_id", "=", customer_id), ("status", "=", "active")], limit=1)
        if not cart or not cart.line_ids:
            # If active cart was already checked out for a pending order, re-use the recent pending order
            recent_pending = env["jabin.order"].sudo().search([
                ("customer_id", "=", customer_id),
                ("state", "=", "pending_payment")
            ], order="id desc", limit=1)
            if recent_pending:
                update_pending_vals = {
                    "slaughter_date": parsed_slaughter_date,
                    "slaughter_time": cleaned_slaughter_time,
                }
                if payment_method_id and payment_method_id != recent_pending.payment_method_id.id:
                    pm = env["jabin.payment.method"].sudo().browse(payment_method_id)
                    if pm.exists() and pm.active and pm.code != "myfatoorah" and pm.provider != "myfatoorah":
                        update_pending_vals["payment_method_id"] = pm.id
                        if pm.code == "cod":
                            update_pending_vals["state"] = "confirmed"
                recent_pending.sudo().write(update_pending_vals)
                return recent_pending
            raise ValidationError(_("السلة فارغة."))

        # Revalidate cart products, sizes, prices, and options against dashboard source of truth
        from odoo.addons.jabin_dashboard.validators.cart_validator import CartValidator
        CartValidator.validate_checkout(cart)

        if delivery_type not in ["address", "pickup"]:
            raise ValidationError(_("delivery_type must be either 'address' or 'pickup'."))

        address_obj = None
        if delivery_type == "address":
            if not address_id:
                address_obj = env["res.users.address"].sudo().search([("user_id", "=", customer_id), ("is_default", "=", True)], limit=1)
                if not address_obj:
                    address_obj = env["res.users.address"].sudo().search([("user_id", "=", customer_id)], limit=1)
                if not address_obj:
                    raise ValidationError(_("عنوان التوصيل مطلوب."))
            else:
                address_obj = env["res.users.address"].sudo().browse(address_id)
                if not address_obj.exists() or address_obj.user_id.id != customer_id:
                    raise ValidationError(_("عنوان التوصيل المختار غير صالح."))

        branch = False
        if delivery_type == "pickup":
            if branch_id:
                branch = env["jabin.branch"].sudo().browse(branch_id)
            if not branch or not branch.exists() or not branch.active:
                branch = env["jabin.branch"].sudo().search([("active", "=", True)], limit=1)
            if not branch:
                branch = env["jabin.branch"].sudo().create({
                    "name": "الفرع الرئيسي",
                    "code": "MAIN",
                    "address": "الرياض، العليا",
                    "city": "الرياض",
                    "active": True,
                })

        if not payment_method_id:
            payment_method = env["jabin.payment.method"].sudo().search([
                ("code", "=", "cod"),
                ("active", "=", True),
            ], limit=1)
            if not payment_method:
                payment_method = env["jabin.payment.method"].sudo().search([
                    ("active", "=", True),
                    ("code", "!=", "myfatoorah"),
                    ("provider", "!=", "myfatoorah"),
                ], limit=1)
            payment_method_id = payment_method.id if payment_method else None
        else:
            payment_method = env["jabin.payment.method"].sudo().browse(payment_method_id)
            if not payment_method.exists() or not payment_method.active:
                raise ValidationError(_("طريقة الدفع المختارة غير متاحة."))
            if payment_method.code == "myfatoorah" or payment_method.provider == "myfatoorah":
                raise ValidationError(_("بوابة ماي فاتورة غير مفعلة، يرجى الدفع عبر بوابة ميسر المعتمدة."))
            ALLOWED_PROVIDERS = ("moyasar", "manual")
            ALLOWED_CODES = ("moyasar", "cod", "card", "mada", "apple_pay", "applepay", "stc_pay")
            if payment_method.provider not in ALLOWED_PROVIDERS and payment_method.code not in ALLOWED_CODES:
                raise ValidationError(_("طريقة الدفع غير معتمدة. يرجى اختيار الدفع الإلكتروني عبر ميسر أو الدفع عند الاستلام."))

        # Determine initial state: COD orders automatically move to confirmed
        initial_state = "confirmed" if (payment_method and payment_method.code == "cod") else "pending_payment"

        # Delivery fee is 0.0 (removed from customer invoices and checkout total per business rule)
        delivery_fee = 0.0

        order_vals = {
            "customer_id": customer_id,
            "state": initial_state,
            "payment_method_id": payment_method_id,
            "internal_notes": notes or cart.notes or "",
            "delivery_type": delivery_type,
            "delivery_fee": delivery_fee,
            "slaughter_date": parsed_slaughter_date,
            "slaughter_time": cleaned_slaughter_time,
        }
        if delivery_type == "pickup" and branch:
            order_vals["branch_id"] = branch.id

        order = env["jabin.order"].sudo().with_context(skip_order_created_notification=True).create(order_vals)

        for line in cart.line_ids:
            size_obj = line.size_id if (hasattr(line, 'size_id') and line.size_id) else None
            size_name = size_obj.name if size_obj else False
            size_price = float(size_obj.price if size_obj else (line.price_unit or 0.0))

            cut_opt = line.cutting_option_id if line.cutting_option_id else None
            cut_name = cut_opt.name if cut_opt else False
            cut_price = float(getattr(cut_opt, "extra_price", 0.0) or 0.0) if cut_opt else 0.0

            pkgs = line.packaging_ids
            pkg_name = "، ".join(pkgs.mapped("name")) if pkgs else False
            pkg_price = sum(float(getattr(p, "extra_price", 0.0) or 0.0) for p in pkgs)

            line_name = f"{line.product_id.name} ({size_name})" if size_name else line.product_id.name
            line_vals = {
                "order_id": order.id,
                "product_id": line.product_id.id,
                "name": line_name,
                "size_id": size_obj.id if size_obj else False,
                "size_name": size_name,
                "size_price": size_price,
                "price_unit": line.price_unit,
                "quantity": line.quantity,
                "discount": line.discount_percent,
                "cutting_option_id": cut_opt.id if cut_opt else False,
                "cutting_option_name": cut_name,
                "cutting_price": cut_price,
                "packaging_id": pkgs.ids[0] if pkgs else False,
                "packaging_ids": [(6, 0, pkgs.ids)] if pkgs else [(5, 0, 0)],
                "packaging_name": pkg_name,
                "packaging_price": pkg_price,
            }
            if line.excluded_part_ids:
                line_vals["excluded_part_ids"] = [(6, 0, line.excluded_part_ids.ids)]

            env["jabin.order.line"].sudo().create(line_vals)

        order._compute_totals()

        # Apply coupon code if provided
        if coupon_code and str(coupon_code).strip():
            order.apply_coupon(str(coupon_code).strip())

        # Redeem loyalty points if requested
        if redeem_points is not None and redeem_points is not False and str(redeem_points).lower() not in ("false", "0", "", "none"):
            from odoo.addons.jabin_dashboard.services.loyalty_service import LoyaltyService
            settings = LoyaltyService.get_settings(env)

            if isinstance(redeem_points, bool) and redeem_points:
                pts = int(user.loyalty_points or 0)
            elif isinstance(redeem_points, str) and redeem_points.lower() in ('true', 'yes'):
                pts = int(user.loyalty_points or 0)
            else:
                try:
                    pts = int(redeem_points)
                except (ValueError, TypeError):
                    pts = int(user.loyalty_points or 0) if bool(redeem_points) else 0

            if pts > 0:
                if int(user.loyalty_points or 0) < settings['min_redemption']:
                    raise ValidationError(
                        _("الحد الأدنى لاستبدال نقاط الولاء هو %(min)s نقطة (رصيدك الحالي %(bal)s نقطة).") % {
                            'min': settings['min_redemption'],
                            'bal': int(user.loyalty_points or 0),
                        }
                    )
                pts = min(pts, int(user.loyalty_points or 0))
                if pts < settings['min_redemption']:
                    raise ValidationError(
                        _("الحد الأدنى لاستبدال نقاط الولاء هو %s نقطة.") % settings['min_redemption']
                    )

                subtotal_before_loyalty = max(
                    0.0,
                    float(order.subtotal or 0.0) - float(order.discount_amount - order.loyalty_discount_amount) + float(order.tax_amount or 0.0)
                )
                max_points_for_order = int(round(subtotal_before_loyalty * settings['redemption_rate']))
                pts = min(pts, max_points_for_order)

                if pts > 0:
                    order.sudo().write({'points_redeemed': pts})
                    order._compute_totals()
                    if 'jabin.loyalty.service' in env:
                        env['jabin.loyalty.service'].deduct_redeemed_points(customer_id, pts, order.id)
                    else:
                        LoyaltyService.deduct_redeemed_points(env, customer_id, pts, order.id)

        order._compute_totals()

        # If order is fully covered by loyalty points / coupon (total <= 0), confirm & mark paid immediately
        if float(order.total or 0.0) <= 0.0:
            order.sudo().write({
                "state": "confirmed",
                "payment_status": "paid",
            })

        order._compute_totals()
        is_online = bool(
            float(order.total or 0.0) > 0.0
            and order.payment_method_id
            and order.payment_method_id.code != "cod"
            and order.payment_method_id.provider not in ("manual", "bank_transfer", False)
        )

        # Cancel any previous abandoned pending_payment orders for this customer so they don't linger
        try:
            old_unpaid_orders = env["jabin.order"].sudo().search([
                ("customer_id", "=", customer_id),
                ("id", "!=", order.id),
                ("state", "=", "pending_payment"),
                ("payment_status", "in", ("pending", "failed")),
            ])
            for old_ord in old_unpaid_orders:
                try:
                    env["jabin.customer.service"].sudo().trigger_status_transition(
                        old_ord.id, "cancelled", description="Cancelled automatically on new checkout attempt."
                    )
                except Exception:
                    old_ord.sudo().write({"state": "cancelled", "payment_status": "cancelled"})
        except Exception:
            pass

        # Keep cart 'active' during online payment redirection so cancelling/closing gateway never wipes the cart!
        # Cart is marked 'checked_out' immediately only for COD / 0-SAR orders, or upon verified Moyasar payment.
        cart.write({
            "status": "active" if is_online else "checked_out",
            "checked_out_order_id": order.id,
            "delivery_address_id": address_obj.id if address_obj else False,
            "slaughter_date": parsed_slaughter_date,
            "slaughter_time": cleaned_slaughter_time,
        })

        try:
            if not is_online:
                env["jabin.notification.service"].sudo().send_order_created(env, order)
        except Exception as notif_err:
            import logging
            logging.getLogger(__name__).warning("Failed to trigger order created notification: %s", notif_err)

        return order
