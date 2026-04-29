from odoo import api, fields, models


class WeighingMixin(models.AbstractModel):
    _name = "weighing.mixin"
    _description = "Mixin for weighed stock operations"

    has_weight = fields.Boolean(
        compute="_compute_has_weight",
        search="_search_has_weight",
    )

    @api.model
    def _has_weigh_domain(self):
        return [
            (
                "product_uom_category_id",
                "=",
                self.env.ref("uom.product_uom_categ_kgm").id,
            ),
        ]

    @api.depends("product_uom_category_id")
    def _compute_has_weight(self):
        weight_category = self.env.ref("uom.product_uom_categ_kgm", raise_if_not_found=False)
        if not weight_category:
            self.has_weight = False
            return
        for record in self:
            record.has_weight = (
                record.product_uom_category_id == weight_category
                if record.product_uom_category_id
                else False
            )

    def _search_has_weight(self, operator, value):
        weight_category = self.env.ref("uom.product_uom_categ_kgm", raise_if_not_found=False)
        if not weight_category:
            return [("id", "=", False)]
        return [
            ("product_uom_category_id", operator, weight_category.id),
        ]
