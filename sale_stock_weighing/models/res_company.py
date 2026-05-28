from odoo import fields, models

_PARAM = "sale_stock_weighing.use_company_{}"


class ResCompany(models.Model):
    _inherit = "res.company"

    use_stock_weighing = fields.Boolean(
        string="Usar pesaje de productos",
        compute="_compute_use_stock_weighing",
        inverse="_inverse_use_stock_weighing",
        help="Activa las columnas de pesaje en órdenes de venta y remitos "
             "para esta empresa. Desactivar oculta toda la funcionalidad de "
             "pesaje para usuarios de esta compañía.",
    )

    def _compute_use_stock_weighing(self):
        """Lee el flag desde ir.config_parameter para evitar columna en res_company."""
        ICP = self.env["ir.config_parameter"].sudo()
        for company in self:
            val = ICP.get_param(_PARAM.format(company.id), "True")
            company.use_stock_weighing = val == "True"

    def _inverse_use_stock_weighing(self):
        """Escribe el flag en ir.config_parameter."""
        ICP = self.env["ir.config_parameter"].sudo()
        for company in self:
            ICP.set_param(_PARAM.format(company.id), str(company.use_stock_weighing))
