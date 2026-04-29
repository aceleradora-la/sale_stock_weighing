from odoo import api, fields, models


class WeighingMixin(models.AbstractModel):
    _name = "weighing.mixin"
    _description = "Mixin for weighed stock operations"

    has_weight = fields.Boolean(
        compute="_compute_has_weight",
        search="_search_has_weight",
    )

    def _get_weight_category(self):
        return self.env.ref("uom.product_uom_categ_kgm", raise_if_not_found=False)

    @api.depends("product_id.uom_id.category_id")
    def _compute_has_weight(self):
        weight_category = self._get_weight_category()
        if not weight_category:
            self.has_weight = False
            return
        for record in self.filtered("product_id"):
            record.has_weight = record.product_id.uom_id.category_id == weight_category
        for record in self.filtered(lambda r: not r.product_id):
            record.has_weight = False

    def _search_has_weight(self, operator, value):
        weight_category = self._get_weight_category()
        if not weight_category:
            return [("id", "=", False)]
        return [
            ("product_id.uom_id.category_id", operator, weight_category.id),
        ]
