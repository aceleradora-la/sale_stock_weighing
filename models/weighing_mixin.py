from odoo import api, fields, models


class WeighingMixin(models.AbstractModel):
    _name = "weighing.mixin"
    _description = "Mixin for weighed stock operations"

    has_weight = fields.Boolean(
        compute="_compute_has_weight",
        search="_search_has_weight",
        store=True,
    )

    @api.depends("product_id.is_weighed_product")
    def _compute_has_weight(self):
        for record in self:
            record.has_weight = bool(record.product_id.is_weighed_product)

    def _search_has_weight(self, operator, value):
        if operator == "=" and value:
            return [("product_id.is_weighed_product", "=", True)]
        elif operator == "=" and not value:
            return [("product_id.is_weighed_product", "=", False)]
        elif operator == "!=" and value:
            return [("product_id.is_weighed_product", "=", False)]
        elif operator == "!=" and not value:
            return [("product_id.is_weighed_product", "=", True)]
        return [("id", "=", False)]
