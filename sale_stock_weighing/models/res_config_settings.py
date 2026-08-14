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
    weighing_default_input_mode = fields.Selection(
        related="company_id.weighing_default_input_mode",
        readonly=False,
        string="Modo de carga por defecto",
    )
    weighing_default_detail_level = fields.Selection(
        related="company_id.weighing_default_detail_level",
        readonly=False,
        string="Nivel de detalle por defecto",
    )
