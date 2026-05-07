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
    x_delivered_piece_count = fields.Integer(
        string="Delivered Pieces",
        help="Number of pieces (units) delivered, for display on the invoice.",
    )


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_recompute_weight_lines(self):
        for invoice in self:
            if invoice.state != "draft":
                continue
            for inv_line in invoice.invoice_line_ids:
                sol = inv_line.sale_line_ids[:1]
                if (
                    sol
                    and sol.product_id.is_weighed_product
                    and sol.total_delivered_weight > 0
                ):
                    inv_line.write(sol._get_weighed_invoice_vals(name=inv_line.name))
