from odoo import api, fields, models, _

class JabinCustomerActivity(models.Model):
    _name = "jabin.customer.activity"
    _description = "JABIN Customer Activity Log"
    _order = "timestamp desc, id desc"

    user_id = fields.Many2one(
        "res.users",
        string="Customer",
        required=True,
        ondelete="cascade",
        index=True
    )
    action = fields.Selection([
        ("registered", "Registered"),
        ("logged_in", "Logged In"),
        ("logged_out", "Logged Out"),
        ("updated_profile", "Updated Profile"),
        ("changed_address", "Changed Address"),
        ("created_order", "Created Order"),
        ("confirmed_order", "Confirmed Order"),
        ("preparing_order", "Preparing Order"),
        ("ready_pickup_order", "Ready for Pickup Order"),
        ("out_delivery_order", "Out for Delivery Order"),
        ("order_delivered", "Order Delivered"),
        ("cancelled_order", "Cancelled Order"),
        ("paid_order", "Paid Order"),
        ("requested_refund", "Requested Refund")
    ], string="Action", required=True, index=True)

    related_record = fields.Reference(selection=[
        ("jabin.order", "Order"),
        ("jabin.payment.transaction", "Payment Transaction"),
        ("res.users", "User"),
        ("res.users.address", "Address")
    ], string="Related Record", index=True)

    timestamp = fields.Datetime(
        string="Timestamp",
        default=fields.Datetime.now,
        required=True,
        index=True
    )
    triggered_by_id = fields.Many2one(
        "res.users",
        string="Triggered By",
        default=lambda self: self.env.user.id,
        required=True
    )
