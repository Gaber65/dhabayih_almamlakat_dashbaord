from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class JabinOrder(models.Model):
    _name = "jabin.order"
    _description = "JABIN Order"
    _order = "date desc, id desc"

    name = fields.Char(
        string="Order Number",
        required=True,
        index=True,
        copy=False,
        default="/",
        readonly=True
    )
    customer_id = fields.Many2one(
        "res.users",
        string="Customer",
        required=True,
        index=True,
        ondelete="restrict",
        domain="[('user_type', 'in', ['individual', 'business'])]"
    )
    date = fields.Datetime(
        string="Order Date",
        default=fields.Datetime.now,
        required=True,
        index=True
    )
    state = fields.Selection([
        ("draft", "Draft"),
        ("pending_payment", "Pending Payment"),
        ("confirmed", "Confirmed"),
        ("preparing", "Preparing"),
        ("ready_pickup", "Ready for Pickup"),
        ("out_delivery", "Out for Delivery"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded")
    ], string="Status", default="draft", required=True, index=True, copy=False)

    payment_status = fields.Selection([
        ("pending", "Pending"),
        ("authorized", "Authorized"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded")
    ], string="Payment Status", default="pending", required=True, index=True, copy=False)

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id.id,
        required=True
    )
    subtotal = fields.Monetary(
        string="Subtotal",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id"
    )
    discount_amount = fields.Monetary(
        string="Discount",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id"
    )
    tax_amount = fields.Monetary(
        string="Tax",
        default=0.0,
        currency_field="currency_id"
    )
    total = fields.Monetary(
        string="Total Amount",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id"
    )
    order_line_ids = fields.One2many(
        "jabin.order.line",
        "order_id",
        string="Order Lines",
        copy=True
    )
    timeline_ids = fields.One2many(
        "jabin.order.timeline",
        "order_id",
        string="Order Timeline",
        readonly=True
    )
    internal_notes = fields.Text(string="Internal Notes")
    payment_method_id = fields.Many2one(
        "jabin.payment.method",
        string="Payment Method",
        ondelete="restrict"
    )
    payment_transaction_ids = fields.One2many(
        "jabin.payment.transaction",
        "order_id",
        string="Payment Transactions"
    )

    @api.depends("order_line_ids.price_subtotal", "order_line_ids.discount", "tax_amount")
    def _compute_totals(self):
        for order in self:
            lines = order.order_line_ids
            subtotal = sum(lines.mapped("price_subtotal"))
            discount = sum(lines.mapped("discount_amount"))
            order.subtotal = subtotal
            order.discount_amount = discount
            order.total = subtotal - discount + order.tax_amount

    # --- Business Action Methods (delegate to service layer) ---
    def _get_service(self):
        return self.env["jabin.customer.service"]

    def action_confirm(self):
        self.ensure_one()
        self._get_service().trigger_status_transition(self.id, "confirmed")

    def action_start_preparing(self):
        self.ensure_one()
        self._get_service().trigger_status_transition(self.id, "preparing")

    def action_mark_ready(self):
        self.ensure_one()
        self._get_service().trigger_status_transition(self.id, "ready_pickup")

    def action_out_for_delivery(self):
        self.ensure_one()
        self._get_service().trigger_status_transition(self.id, "out_delivery")

    def action_mark_delivered(self):
        self.ensure_one()
        self._get_service().trigger_status_transition(self.id, "delivered")

    def action_cancel(self):
        self.ensure_one()
        self._get_service().trigger_status_transition(self.id, "cancelled")

    def action_refund(self):
        self.ensure_one()
        self._get_service().trigger_status_transition(self.id, "refunded")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                seq = self.env["ir.sequence"].next_by_code("jabin.order")
                if seq:
                    vals["name"] = seq
                else:
                    import random
                    date_str = fields.Datetime.now().strftime("%Y%m%d")
                    vals["name"] = f"JAB-ORD-{date_str}-{random.randint(1000, 9999)}"
        orders = super().create(vals_list)
        for order in orders:
            # Generate initial timeline entry
            self.env["jabin.order.timeline"].create({
                "order_id": order.id,
                "status_to": order.state,
                "description": _("Order created as %s.") % order.state,
            })
            # Log customer activity
            order.customer_id.log_activity("created_order", related_record=f"jabin.order,{order.id}")
        return orders


class JabinOrderLine(models.Model):
    _name = "jabin.order.line"
    _description = "JABIN Order Line"

    order_id = fields.Many2one(
        "jabin.order",
        string="Order",
        required=True,
        ondelete="cascade",
        index=True
    )
    name = fields.Char(string="Description", required=True)
    price_unit = fields.Float(string="Unit Price", default=0.0, required=True)
    quantity = fields.Float(string="Quantity", default=1.0, required=True)
    discount = fields.Float(string="Discount (%)", default=0.0)
    currency_id = fields.Many2one(
        "res.currency",
        related="order_id.currency_id",
        store=True,
        readonly=True
    )
    price_subtotal = fields.Monetary(
        string="Subtotal",
        compute="_compute_subtotal",
        store=True,
        currency_field="currency_id"
    )
    discount_amount = fields.Monetary(
        string="Discount Amount",
        compute="_compute_subtotal",
        store=True,
        currency_field="currency_id"
    )

    @api.depends("price_unit", "quantity", "discount")
    def _compute_subtotal(self):
        for line in self:
            base = line.price_unit * line.quantity
            line.discount_amount = base * (line.discount / 100.0)
            line.price_subtotal = base - line.discount_amount


class JabinOrderTimeline(models.Model):
    _name = "jabin.order.timeline"
    _description = "JABIN Order Status Timeline"
    _order = "timestamp desc, id desc"

    order_id = fields.Many2one(
        "jabin.order",
        string="Order",
        required=True,
        ondelete="cascade",
        index=True
    )
    status_from = fields.Selection([
        ("draft", "Draft"),
        ("pending_payment", "Pending Payment"),
        ("confirmed", "Confirmed"),
        ("preparing", "Preparing"),
        ("ready_pickup", "Ready for Pickup"),
        ("out_delivery", "Out for Delivery"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded")
    ], string="From Status")
    status_to = fields.Selection([
        ("draft", "Draft"),
        ("pending_payment", "Pending Payment"),
        ("confirmed", "Confirmed"),
        ("preparing", "Preparing"),
        ("ready_pickup", "Ready for Pickup"),
        ("out_delivery", "Out for Delivery"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded")
    ], string="To Status", required=True)
    description = fields.Text(string="Action Details")
    timestamp = fields.Datetime(
        string="Timestamp",
        default=fields.Datetime.now,
        required=True,
        index=True
    )
    triggered_by_id = fields.Many2one(
        "res.users",
        string="Action By",
        default=lambda self: self.env.user.id,
        required=True
    )
