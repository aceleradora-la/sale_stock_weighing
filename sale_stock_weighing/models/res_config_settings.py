from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    use_stock_weighing = fields.Boolean(
        related="company_id.use_stock_weighing",
        readonly=False,
        string="Usar pesaje de productos",
        help="Activa las columnas de pesaje en órdenes de venta y remitos "
             "para esta empresa.",
    )
