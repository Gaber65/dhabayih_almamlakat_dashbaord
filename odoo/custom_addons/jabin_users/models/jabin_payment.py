from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class JabinPaymentMethod(models.Model):
    _name = "jabin.payment.method"
    _description = "JABIN Payment Method"
    _order = "name"

    name = fields.Char(string="Name", required=True, translate=True)
    code = fields.Char(string="Code", required=True, index=True)
    payment_type = fields.Selection([
        ("cash", "Cash on Delivery"),
        ("card", "Card (Visa / Mastercard)"),
        ("wallet", "Digital Wallet"),
        ("installment", "Installment (BNPL)")
    ], string="Payment Type", default="cash", required=True)
    provider = fields.Selection([
        ("manual", "Cash on Delivery / Manual"),
        ("tamara", "Tamara"),
        ("tabby", "Tabby"),
        ("stripe", "Stripe Gateway"),
        ("mada", "Mada Gateway"),
        ("stc_pay", "STC Pay"),
        ("mock", "Mock Gateway")
    ], string="Provider", default="manual", required=True)
    is_installment = fields.Boolean(string="Supports Installments", default=False)
    max_installments = fields.Integer(string="Max Installments", default=0)
    active = fields.Boolean(string="Active", default=True)
    description = fields.Text(string="Description")

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Payment method code must be unique!")
    ]


class JabinPaymentTransaction(models.Model):
    _name = "jabin.payment.transaction"
    _description = "JABIN Payment Transaction"
    _order = "id desc"

    order_id = fields.Many2one(
        "jabin.order",
        string="Order",
        required=True,
        ondelete="restrict",
        index=True
    )
    customer_id = fields.Many2one(
        "res.users",
        string="Customer",
        required=True,
        ondelete="restrict",
        index=True,
        domain="[('user_type', 'in', ['individual', 'business'])]"
    )
    payment_method_id = fields.Many2one(
        "jabin.payment.method",
        string="Payment Method",
        required=True,
        ondelete="restrict"
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="order_id.currency_id",
        store=True,
        readonly=True
    )
    amount = fields.Monetary(
        string="Amount",
        required=True,
        currency_field="currency_id"
    )
    status = fields.Selection([
        ("pending", "Pending"),
        ("authorized", "Authorized"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded")
    ], string="Status", default="pending", required=True, index=True)

    transaction_ref = fields.Char(string="Transaction Reference", index=True)
    paid_date = fields.Datetime(string="Paid Date")
    failure_reason = fields.Char(string="Failure Reason")
    refund_status = fields.Selection([
        ("none", "No Refund"),
        ("partial", "Partially Refunded"),
        ("full", "Fully Refunded")
    ], string="Refund Status", default="none", required=True)

    # Installment specific fields
    is_installment = fields.Boolean(
        string="Is Installment",
        related="payment_method_id.is_installment",
        store=True,
        readonly=True
    )
    installment_status = fields.Selection([
        ("pending", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("settled", "Settled")
    ], string="Installment Status")
    installment_provider = fields.Selection([
        ("tamara", "Tamara"),
        ("tabby", "Tabby")
    ], string="Installment Provider")
    installment_approval_status = fields.Char(string="Installment Approval Detail")
    num_installments = fields.Integer(string="Installments Count", default=1)

    def action_collect_cod(self):
        """Business action: settle a Cash on Delivery transaction."""
        self.ensure_one()
        self.env["jabin.customer.service"].collect_cod_cash(self.id)
