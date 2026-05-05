from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_weighed_product = fields.Boolean(
        string="Weighed Product",
        help="If checked, this product will use the weighing flow. "
        "Sale by units, deliver and invoice by weight.",
    )
    weighing_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Weighing UoM",
        help="Unit of measure used for weighing (e.g. kg). "
        "Price is per this unit.",
    )

    @api.onchange("is_weighed_product")
    def _onchange_is_weighed_product(self):
        if self.is_weighed_product and not self.weighing_uom_id:
            kg_uom = self.env.ref("uom.product_uom_kgm", raise_if_not_found=False)
            if kg_uom:
                self.weighing_uom_id = kg_uom


class ProductProduct(models.Model):
    _inherit = "product.product"

    is_weighed_product = fields.Boolean(
        related="product_tmpl_id.is_weighed_product", store=True
    )
    weighing_uom_id = fields.Many2one(
        related="product_tmpl_id.weighing_uom_id", store=True
    )
