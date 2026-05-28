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
        """Escribe el flag en ir.config_parameter y sincroniza el grupo de pesaje."""
        ICP = self.env["ir.config_parameter"].sudo()
        for company in self:
            ICP.set_param(_PARAM.format(company.id), str(company.use_stock_weighing))
        self._sync_weighing_group()

    def _sync_weighing_group(self):
        """Sincroniza la membresía en group_use_weighing según la config por empresa.

        Un usuario entra al grupo si AL MENOS UNA de sus empresas tiene
        use_stock_weighing = True. Esto garantiza que en entornos multiempresa,
        un usuario que pertenece a varias compañías solo pierda acceso al menú
        de pesaje cuando NINGUNA de sus compañías usa pesaje.
        """
        group = self.env.ref(
            "sale_stock_weighing.group_use_weighing", raise_if_not_found=False
        )
        if not group:
            return
        ICP = self.env["ir.config_parameter"].sudo()
        all_users = self.env["res.users"].sudo().search([
            ("share", "=", False),
            ("active", "=", True),
        ])
        to_add = []
        to_remove = []
        for user in all_users:
            has_weighing = any(
                ICP.get_param(_PARAM.format(c.id), "True") == "True"
                for c in user.company_ids
            )
            if has_weighing:
                to_add.append(user.id)
            else:
                to_remove.append(user.id)
        if to_add:
            group.sudo().write({"users": [(4, uid) for uid in to_add]})
        if to_remove:
            group.sudo().write({"users": [(3, uid) for uid in to_remove]})
