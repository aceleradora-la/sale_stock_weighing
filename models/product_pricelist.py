from odoo import api, fields, models


class Pricelist(models.Model):
    _inherit = "product.pricelist"

    def _get_matched_weighing_items(self, product):
        self.ensure_one()
        category_ids = set()
        cat = product.categ_id
        while cat:
            category_ids.add(cat.id)
            cat = cat.parent_id

        items = self.item_ids.filtered(
            lambda i: i.is_weighed_price
            and (
                (i.applied_on == "0_product_variant" and i.product_id == product)
                or (i.applied_on == "1_product" and i.product_tmpl_id == product.product_tmpl_id)
                or (i.applied_on == "2_product_category" and i.categ_id.id in category_ids)
                or i.applied_on == "3_global"
            )
        )
        return items.sorted("min_quantity", reverse=True)

    def _get_product_price(self, product, quantity=1.0, *args, **kwargs):
        self.ensure_one()
        if product.is_weighed_product:
            matched = self._get_matched_weighing_items(product)
            if matched:
                return matched[0].compute_price_per_weight(product, quantity)
        return super()._get_product_price(product, quantity, *args, **kwargs)


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
            item.weighing_uom_name = (
                item.product_id.weighing_uom_id.name
                or item.product_tmpl_id.weighing_uom_id.name
                or "kg"
            )

    def compute_price_per_weight(self, product, quantity=1):
        self.ensure_one()
        if not self.is_weighed_price:
            return 0.0
        if self.compute_price == "fixed":
            return self.price_per_weight
        if self.compute_price in ("discount", "formula"):
            base_price = self._compute_base_price_for_weight(product)
            if base_price <= 0 and self.compute_price == "discount":
                return 0.0
            # discount subtracts the percentage, formula adds it (markup).
            sign = -1 if self.compute_price == "discount" else 1
            result = base_price * (1 + sign * (self.price_discount or 0) / 100)
            result += self.price_surcharge or 0.0
            cost = product.standard_price or 0.0
            if self.price_min_margin:
                result = max(result, cost + self.price_min_margin)
            if self.price_max_margin:
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
