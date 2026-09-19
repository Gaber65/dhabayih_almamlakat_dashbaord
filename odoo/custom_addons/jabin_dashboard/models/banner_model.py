from odoo import api, fields, models

class Banner(models.Model):
    _name = "banner"
    _description = "Banner"

    image = fields.Image(
        string="Banner Image",
        max_width=1920,
        max_height=800,
    )

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    
    banner_type = fields.Selection([
        ("offer", "Promotional Offer"),
        ("category", "Category"),
        ("product", "Single Product"),
        ("custom", "Custom Link")
    ], string="Banner Type", default="offer", required=True)
    
    offer_id = fields.Many2one(
        "jabin.offer",
        string="Linked Offer",
        ondelete="set null",
        help="When clicked, navigates directly to this offer and its discounted products."
    )
    category_id = fields.Many2one("jabin.category", string="Linked Category", ondelete="set null")
    product_id = fields.Many2one("jabin.product", string="Linked Product", ondelete="set null")
    deep_link = fields.Char(string="App Deep Link", compute="_compute_deep_link", store=True, readonly=False)

    @api.depends("banner_type", "offer_id", "category_id", "product_id")
    def _compute_deep_link(self):
        for rec in self:
            if not rec.deep_link:
                if rec.banner_type == "offer" and rec.offer_id:
                    rec.deep_link = f"jabin://offers/{rec.offer_id.id}"
                elif rec.banner_type == "category" and rec.category_id:
                    rec.deep_link = f"jabin://categories/{rec.category_id.id}"
                elif rec.banner_type == "product" and rec.product_id:
                    rec.deep_link = f"jabin://products/{rec.product_id.id}"
                else:
                    rec.deep_link = "jabin://offers"

    @api.model_create_multi
    def create(self, vals_list):
        records = super(Banner, self).create(vals_list)
        for record in records:
            if record.active:
                try:
                    self.env["jabin.notification.service"].sudo().send_new_banner(self.env, record)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error("Failed to send banner notification: %s", e)
        return records