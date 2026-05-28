from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    company_use_stock_weighing = fields.Boolean(
        related="company_id.use_stock_weighing",
        string="Empresa usa pesaje",
        # store=False (computed): solo se usa para column_invisible en la vista
    )
