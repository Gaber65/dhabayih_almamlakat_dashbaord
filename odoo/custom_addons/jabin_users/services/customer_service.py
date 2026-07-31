from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class JabinCustomerService(models.AbstractModel):
    _name = "jabin.customer.service"
    _description = "JABIN Customer Operations Service"

    # Define valid transitions for state safety
    STATE_TRANSITIONS = {
        "draft": ["pending_payment", "confirmed", "cancelled"],
        "pending_payment": ["confirmed", "cancelled"],
        "confirmed": ["preparing", "cancelled"],
        "preparing": ["ready_pickup", "cancelled"],
        "ready_pickup": ["out_delivery", "cancelled"],
        "out_delivery": ["delivered", "cancelled"],
        "delivered": ["refunded"],
        "cancelled": [],
        "refunded": []
    }

    @api.model
    def create_order(self, customer_id, line_vals_list, payment_method_code, internal_notes=None):
        """
        Orchestrates order and order lines creation.
        """
        if not customer_id:
            raise ValidationError(_("Customer is required."))
        if not line_vals_list:
            raise ValidationError(_("Order lines are required."))

        customer = self.env["res.users"].browse(customer_id)
        if not customer.exists():
            raise ValidationError(_("Customer does not exist."))

        payment_method = self.env["jabin.payment.method"].search([("code", "=", payment_method_code)], limit=1)
        if not payment_method:
            raise ValidationError(_("Payment method '%s' not found.") % payment_method_code)

        # Build order vals
        order_vals = {
            "customer_id": customer.id,
            "payment_method_id": payment_method.id,
            "internal_notes": internal_notes,
            "state": "draft",
            "payment_status": "pending",
        }

        # Build lines
        lines_list = []
        for line in line_vals_list:
            lines_list.append((0, 0, {
                "name": line.get("name"),
                "price_unit": line.get("price_unit", 0.0),
                "quantity": line.get("quantity", 1.0),
                # If product_id is passed, it will be saved correctly on the extended model (in jabin_dashboard)
                "product_id": line.get("product_id")
            }))
        order_vals["order_line_ids"] = lines_list

        order = self.env["jabin.order"].sudo().create(order_vals)
        if "jabin.notification.service" in self.env:
            try:
                self.env["jabin.notification.service"].send_order_created(self.env, order)
            except Exception:
                pass
        return order

    @api.model
    def trigger_status_transition(self, order_id, new_state, description=None):
        """
        Triggers a business state transition, updates status timeline, and logs activity.
        """
        order = self.env["jabin.order"].browse(order_id)
        if not order.exists():
            raise ValidationError(_("Order %s not found.") % order_id)

        old_state = order.state
        if old_state == new_state:
            return True

        allowed = self.STATE_TRANSITIONS.get(old_state, [])
        if new_state not in allowed:
            raise ValidationError(_("Invalid status transition from '%s' to '%s'.") % (old_state, new_state))

        # Perform update
        order.sudo().write({"state": new_state})

        # Record in timeline
        self.env["jabin.order.timeline"].sudo().create({
            "order_id": order.id,
            "status_from": old_state,
            "status_to": new_state,
            "description": description or _("Status updated from %s to %s.") % (old_state, new_state)
        })

        # Log activities for key stages and handle loyalty points & push notifications
        if new_state == "delivered":
            order.customer_id.log_activity("order_delivered", related_record=f"jabin.order,{order.id}")
            if "jabin.loyalty.service" in self.env:
                self.env["jabin.loyalty.service"].award_earned_points(self.env, order.id)
        elif new_state == "cancelled":
            order.customer_id.log_activity("cancelled_order", related_record=f"jabin.order,{order.id}")
            if order.payment_status in ("pending", "authorized"):
                order.sudo().write({"payment_status": "cancelled"})
            if "jabin.loyalty.service" in self.env:
                self.env["jabin.loyalty.service"].reverse_order_points(self.env, order.id)
        elif new_state == "refunded":
            order.customer_id.log_activity("requested_refund", related_record=f"jabin.order,{order.id}")
            order.sudo().write({"payment_status": "refunded"})
            # Mark all paid transactions related to this order as refunded
            transactions = self.env["jabin.payment.transaction"].search([
                ("order_id", "=", order.id),
                ("status", "=", "paid")
            ])
            transactions.sudo().write({"status": "refunded", "refund_status": "full"})
            if "jabin.loyalty.service" in self.env:
                self.env["jabin.loyalty.service"].reverse_order_points(self.env, order.id)

        if "jabin.notification.service" in self.env:
            try:
                self.env["jabin.notification.service"].send_order_status_changed(self.env, order, new_state)
            except Exception:
                pass

        return True


    @api.model
    def process_payment_transaction(self, order_id, status, ref=None, failure_reason=None, installment_info=None):
        """
        Creates a payment transaction record and transitions order payment status.
        """
        order = self.env["jabin.order"].browse(order_id)
        if not order.exists():
            raise ValidationError(_("Order %s not found.") % order_id)

        vals = {
            "order_id": order.id,
            "customer_id": order.customer_id.id,
            "payment_method_id": order.payment_method_id.id,
            "amount": order.total,
            "status": status,
            "transaction_ref": ref,
            "failure_reason": failure_reason,
            "paid_date": fields.Datetime.now() if status == "paid" else None
        }

        # Apply installment details if present
        if installment_info and order.payment_method_id.is_installment:
            vals.update({
                "installment_status": installment_info.get("status", "pending"),
                "installment_provider": order.payment_method_id.provider,
                "installment_approval_status": installment_info.get("approval_status"),
                "num_installments": installment_info.get("num_installments", 1)
            })

        tx = self.env["jabin.payment.transaction"].sudo().create(vals)

        # Sync transaction status back to order
        if status == "paid":
            order.sudo().write({"payment_status": "paid"})
            # Auto-confirm the order if it was in draft/pending_payment status
            if order.state in ("draft", "pending_payment"):
                self.trigger_status_transition(order.id, "confirmed", _("Auto-confirmed upon payment verification."))
            order.customer_id.log_activity("paid_order", related_record=f"jabin.payment.transaction,{tx.id}")
            if "jabin.notification.service" in self.env:
                try:
                    self.env["jabin.notification.service"].send_payment_success(self.env, order, tx)
                except Exception:
                    pass
        elif status == "authorized":
            order.sudo().write({"payment_status": "authorized"})
        elif status == "failed":
            order.sudo().write({"payment_status": "failed"})
            if "jabin.notification.service" in self.env:
                try:
                    self.env["jabin.notification.service"].send_payment_failed(self.env, order, tx)
                except Exception:
                    pass

        return tx


    @api.model
    def collect_cod_cash(self, transaction_id):
        """
        Settles Cash on Delivery payment collection.
        """
        tx = self.env["jabin.payment.transaction"].browse(transaction_id)
        if not tx.exists():
            raise ValidationError(_("Transaction %s not found.") % transaction_id)
        if tx.payment_method_id.code != "cod":
            raise ValidationError(_("This action is only valid for Cash on Delivery transactions."))

        if tx.status == "paid":
            return True

        tx.sudo().write({
            "status": "paid",
            "paid_date": fields.Datetime.now()
        })
        tx.order_id.sudo().write({"payment_status": "paid"})
        tx.customer_id.log_activity("paid_order", related_record=f"jabin.payment.transaction,{tx.id}")
        return True
