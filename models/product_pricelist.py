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
        help="Apply pricing rules to price per kg instead of price per unit.",
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

    def compute_price_per_weight(self, product, quantity=1):
        self.ensure_one()
        if not self.is_weighed_price:
            return 0.0

        if self.compute_price == "fixed":
            return self.price_per_weight

        if self.compute_price == "discount":
            base_price = self._compute_base_price_for_weight(product)
            if base_price <= 0:
                return 0.0
            discount = self.price_discount if self.price_discount > 0 else 0
            result = base_price * (1 - discount / 100)
            result += self.price_surcharge
            if self.price_min_margin:
                cost = product.standard_price or 0.0
                result = max(result, cost + self.price_min_margin)
            if self.price_max_margin:
                cost = product.standard_price or 0.0
                result = min(result, cost + self.price_max_margin)
            return result

        if self.compute_price == "formula":
            base_price = self._compute_base_price_for_weight(product)
            margin = self.price_discount
            result = base_price * (1 + margin / 100)
            result += self.price_surcharge
            if self.price_min_margin:
                cost = product.standard_price or 0.0
                result = max(result, cost + self.price_min_margin)
            if self.price_max_margin:
                cost = product.standard_price or 0.0
                result = min(result, cost + self.price_max_margin)
            return result

        return 0.0

    def _compute_base_price_for_weight(self, product):
        self.ensure_one()
        if self.base == "pricelist" and self.base_pricelist_id:
            return self.base_pricelist_id._get_product_price(product, 1.0)
        if self.base == "standard_price":
            return product.standard_price or 0.0
        if self.base == "list_price":
            return product.list_price or 0.0
        return 0.0
