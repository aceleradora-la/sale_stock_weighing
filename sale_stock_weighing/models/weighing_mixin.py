from odoo import api, fields, models


class WeighingMixin(models.AbstractModel):
    _name = "weighing.mixin"
    _description = "Mixin para operaciones de pesaje"

    has_weight = fields.Boolean(
        compute="_compute_has_weight",
        store=True,
    )

    @api.depends("product_id.is_weighed_product")
    def _compute_has_weight(self):
        for record in self:
            record.has_weight = bool(record.product_id.is_weighed_product)
