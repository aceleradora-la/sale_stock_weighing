from odoo import api, fields, models
from odoo.tools import float_round


class Pricelist(models.Model):
    _inherit = "product.pricelist"

    def _get_matched_weighing_items(self, product):
        self.ensure_one()
        category_ids = product.categ_id._get_recursive_parent_ids() | product.categ_id
        items = self.item_ids.filtered(
            lambda i: i.is_weighed_price
            and (
                (i.applied_on == "0_product_variant" and i.product_id == product)
                or (i.applied_on == "1_product" and i.product_tmpl_id == product.product_tmpl_id)
                or (i.applied_on == "2_product_category" and i.categ_id in category_ids)
                or i.applied_on == "3_global"
            )
        )
        return items.sorted("min_quantity", reverse=True)

    def _get_product_price(self, product, quantity=1):
        self.ensure_one()
        result = self._get_matched_weighing_items(product)
        if result:
            return result[0].compute_price_per_weight(product, quantity)
        return product.list_price or 0.0


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
    ppw_compute_price = fields.Selection(
        selection=[
            ("fixed", "Fixed Price"),
            ("formula", "Formula"),
        ],
        default="fixed",
        string="Weight Price Computation",
        help="How to compute the price per weight unit.",
    )
    ppw_base = fields.Selection(
        selection=[
            ("list_price", "Public Price"),
            ("standard_price", "Cost"),
            ("pricelist", "Other Pricelist"),
        ],
        default="list_price",
        string="Weight Price Based On",
        help="Base price for computing the weight price (Formula mode only).",
    )
    ppw_pricelist_id = fields.Many2one(
        comodel_name="product.pricelist",
        string="Based on Pricelist",
        help="Other pricelist to use as base for weight price.",
    )
    ppw_percent_price = fields.Float(
        string="Margin / Discount (%)",
        help="Percentage to apply over the base price. "
        "Positive = markup, negative = discount. "
        "Result = base × (1 + percent/100).",
    )
    ppw_price_surcharge = fields.Float(
        string="Extra Price (per weight)",
        digits="Product Price",
        help="Fixed surcharge added to the final price per weight unit.",
    )
    ppw_price_min_margin = fields.Float(
        string="Min. Margin",
        help="Minimum margin to guarantee on cost.",
    )
    ppw_price_max_margin = fields.Float(
        string="Max. Margin",
        help="Maximum margin allowed on cost.",
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

    @api.onchange("ppw_compute_price")
    def _onchange_ppw_compute_price(self):
        if self.ppw_compute_price == "fixed":
            self.ppw_base = False
            self.ppw_pricelist_id = False
            self.ppw_percent_price = 0
            self.ppw_price_surcharge = 0
            self.ppw_price_min_margin = 0
            self.ppw_price_max_margin = 0
        else:
            self.ppw_base = "list_price"

    def compute_price_per_weight(self, product, quantity=1):
        self.ensure_one()
        if not self.is_weighed_price:
            return 0.0
        if self.ppw_compute_price == "fixed":
            return self.price_per_weight
        result = self._compute_base_price_per_weight(product)
        result = result * (1 + self.ppw_percent_price / 100)
        result += self.ppw_price_surcharge
        if self.ppw_price_min_margin:
            cost = product.standard_price or 0.0
            result = max(result, cost + self.ppw_price_min_margin)
        if self.ppw_price_max_margin:
            cost = product.standard_price or 0.0
            result = min(result, cost + self.ppw_price_max_margin)
        return result

    def _compute_base_price_per_weight(self, product):
        self.ensure_one()
        if self.ppw_base == "list_price":
            return product.list_price or 0.0
        if self.ppw_base == "standard_price":
            return product.standard_price or 0.0
        if self.ppw_base == "pricelist" and self.ppw_pricelist_id:
            return self.ppw_pricelist_id._get_product_price(product, 1.0)
        return 0.0
