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
