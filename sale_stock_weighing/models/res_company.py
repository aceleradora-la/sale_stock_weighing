from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    use_stock_weighing = fields.Boolean(
        string="Usar pesaje de productos",
        default=True,
        help="Activa el pesaje de productos (vender por unidad, entregar y facturar "
             "por peso). Al desactivar se ocultan las columnas de pesaje en órdenes "
             "de venta, remitos y facturas para esta empresa.",
    )
