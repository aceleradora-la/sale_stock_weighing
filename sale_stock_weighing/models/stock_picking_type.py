import ast

from odoo import _, api, fields, models
from odoo.fields import Domain


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    weighing_operations = fields.Boolean(
        string="Operaciones de Pesaje",
        help="Habilita el asistente de pesaje para operaciones de este tipo. "
        "Los productos con UdM de pesaje usarán el flujo de pesaje.",
    )
    weighing_input_mode = fields.Selection(
        selection=[
            ("cards", "Tarjetas"),
            ("grid", "Grilla"),
        ],
        string="Modo de carga",
        default=lambda self: self.env.company.weighing_default_input_mode or "cards",
        help="Tarjetas: se pesa una operación por vez, con el asistente. "
        "Grilla: todas las líneas pesables en una lista editable.",
    )
    weighing_detail_level = fields.Selection(
        selection=[
            ("line", "Total por línea"),
            ("piece", "Detalle por pieza"),
        ],
        string="Nivel de detalle",
        default=lambda self: self.env.company.weighing_default_detail_level or "line",
        help="Total por línea: se carga un peso por línea. "
        "Detalle por pieza: se carga el peso de cada unidad y el total se suma solo.",
    )
    print_weighing_label = fields.Boolean(
        string="Imprimir Etiqueta Automáticamente",
        help="Imprime automáticamente la etiqueta de pesaje al registrar el peso",
    )
    weighing_label_format = fields.Selection(
        selection=[
            ("pdf", "PDF"),
            ("zpl", "ZPL"),
        ],
        default="pdf",
        string="Formato de Etiqueta",
    )
    weight_move_ids = fields.Many2many(
        comodel_name="stock.move",
        compute="_compute_weight_move_ids",
    )
    to_do_weights = fields.Integer(
        compute="_compute_to_do_weights",
    )

    def _compute_weight_move_ids(self):
        any_operation_actions = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sale_stock_weighing.any_operation_actions")
        )
        domain = Domain("state", "in", ("assigned", "confirmed", "waiting"))
        if not any_operation_actions:
            domain &= Domain("has_weight", "=", True)
        for picking_type in self:
            picking_type.weight_move_ids = self.env["stock.move"].search(
                Domain("picking_type_id", "=", picking_type.id) & domain
            )

    @api.depends("weight_move_ids")
    def _compute_to_do_weights(self):
        for picking_type in self:
            picking_type.to_do_weights = len(picking_type.weight_move_ids)

    def _apply_weighing_view_mode(self, action):
        """Ordena las vistas de la acción de pesaje según el modo configurado:
        grilla abre en lista editable, tarjetas abre en kanban."""
        self.ensure_one()
        order = (
            ["list", "kanban", "form"]
            if self.weighing_input_mode == "grid"
            else ["kanban", "list", "form"]
        )
        view_map = {mode: view_id for view_id, mode in action.get("views") or []}
        action["views"] = [(view_map.get(m), m) for m in order if m in view_map]
        action["view_mode"] = ",".join(order)
        return action

    def action_weighing_operations(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sale_stock_weighing.weighing_operation_action"
        )
        self._apply_weighing_view_mode(action)
        action["name"] = _("Pesaje de %(name)s", name=self.name)
        action["domain"] = [("id", "in", self.weight_move_ids.ids)]
        action["context"] = dict(
            self.env.context,
            **ast.literal_eval(action.get("context", "{}") or "{}"),
            group_by=["picking_id"],
        )
        return action
