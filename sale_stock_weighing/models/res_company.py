from odoo import fields, models
from odoo.fields import Command

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

    weighing_default_input_mode = fields.Selection(
        selection=[
            ("cards", "Tarjetas"),
            ("grid", "Grilla"),
        ],
        string="Modo de carga por defecto",
        default="cards",
        help="Valor con el que se crean los tipos de operación nuevos. "
        "Tarjetas: una operación por vez, pensado para depósito con balanza. "
        "Grilla: todas las líneas juntas, pensado para carga administrativa.",
    )
    weighing_default_detail_level = fields.Selection(
        selection=[
            ("line", "Total por línea"),
            ("piece", "Detalle por pieza"),
        ],
        string="Nivel de detalle por defecto",
        default="line",
        help="Valor con el que se crean los tipos de operación nuevos.",
    )

    def _compute_use_stock_weighing(self):
        """Lee el flag desde ir.config_parameter para evitar columna en res_company."""
        ICP = self.env["ir.config_parameter"].sudo()
        for company in self:
            val = ICP.get_param(_PARAM.format(company.id), "True")
            company.use_stock_weighing = val == "True"

    def _inverse_use_stock_weighing(self):
        """Escribe el flag en ir.config_parameter y sincroniza el grupo y tipos de operación."""
        ICP = self.env["ir.config_parameter"].sudo()
        for company in self:
            ICP.set_param(_PARAM.format(company.id), str(company.use_stock_weighing))
        self._sync_weighing_group()
        self._sync_weighing_picking_types()

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
        to_add = self.env["res.users"]
        to_remove = self.env["res.users"]
        for user in all_users:
            has_weighing = any(
                ICP.get_param(_PARAM.format(c.id), "True") == "True"
                for c in user.company_ids
            )
            if has_weighing:
                to_add |= user
            else:
                to_remove |= user
        if to_add:
            to_add.sudo().write({"group_ids": [Command.link(group.id)]})
        if to_remove:
            to_remove.sudo().write({"group_ids": [Command.unlink(group.id)]})

    def _sync_weighing_picking_types(self):
        """Activa/desactiva weighing_operations en todos los tipos de operación
        de salida (outgoing) de cada empresa según use_stock_weighing."""
        for company in self:
            outgoing_types = self.env["stock.picking.type"].sudo().search([
                ("company_id", "=", company.id),
                ("code", "=", "outgoing"),
            ])
            if outgoing_types:
                outgoing_types.write({
                    "weighing_operations": company.use_stock_weighing,
                })
