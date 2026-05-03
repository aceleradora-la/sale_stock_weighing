from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    recorded_weight = fields.Float(
        string="Recorded Weight",
        digits="Product Unit of Measure",
        help="Actual weight delivered and invoiced.",
    )
    weight_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Weight UoM",
        help="Unit of measure for the recorded weight.",
    )
    weight_uom_name = fields.Char(
        string="Weight UoM Name",
        related="weight_uom_id.name",
    )


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_recompute_weight_lines(self):
        for invoice in self:
            if invoice.state != "draft":
                continue
            for inv_line in invoice.invoice_line_ids:
                if not inv_line.sale_line_ids:
                    continue
                for sol in inv_line.sale_line_ids:
                    if (
                        sol.product_id.is_weighed_product
                        and sol.total_delivered_weight > 0
                    ):
                        inv_line.write({
                            "quantity": sol.total_delivered_weight,
                            "price_unit": sol.price_per_weight,
                            "product_uom_id": sol.product_id.weighing_uom_id.id,
                            "recorded_weight": sol.total_delivered_weight,
                            "weight_uom_id": sol.product_id.weighing_uom_id.id,
                        })

