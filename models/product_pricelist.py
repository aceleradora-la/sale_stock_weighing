from odoo import api, fields, models


class PricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    price_per_weight = fields.Float(
        string="Price per Weight Unit",
        digits="Product Price",
        help="Price per weight unit (e.g. per kg) for weighed products.",
    )
    is_weighed_price = fields.Boolean(
        string="Weighed Product Price",
        help="Use price per kg instead of fixed price per unit.",
    )
    weighing_uom_name = fields.Char(
        string="Weight UoM",
        compute="_compute_weighing_uom_name",
    )

    @api.depends("product_id.weighing_uom_id")
    def _compute_weighing_uom_name(self):
        for item in self:
            if item.product_id.weighing_uom_id:
                item.weighing_uom_name = item.product_id.weighing_uom_id.name
            else:
                item.weighing_uom_name = "kg"
