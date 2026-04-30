from odoo import api, fields, models


class PricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    price_per_weight = fields.Float(
        string="Price per Weight Unit",
        digits="Product Price",
        help="Price per weight unit (e.g. per kg) for weighed products. "
        "Used when the product is sold by units but invoiced by actual weight.",
    )
    is_weighed_price = fields.Boolean(
        string="Weighed Product Price",
        help="Check this to use this price for weighed products. "
        "The price will be applied per kg (or weight UoM).",
    )
