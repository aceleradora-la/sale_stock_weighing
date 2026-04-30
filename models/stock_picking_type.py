import ast

from odoo import _, api, fields, models
from odoo.osv import expression


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    weighing_operations = fields.Boolean(
        string="Weighing Operations",
        help="Enable weighing assistant for operations of this type. "
        "Products with weight UoM will use the weighing flow.",
    )
    print_weighing_label = fields.Boolean(
        string="Auto Print Weighing Label",
        help="Automatically print the weight label after recording weight",
    )
    weighing_label_format = fields.Selection(
        selection=[
            ("pdf", "PDF"),
            ("zpl", "ZPL"),
        ],
        default="pdf",
        string="Weighing Label Format",
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
        domain = [("state", "in", ("assigned", "confirmed", "waiting"))]
        if not any_operation_actions:
            domain = expression.AND([domain, [("has_weight", "=", True)]])
        for picking_type in self:
            picking_type.weight_move_ids = self.env["stock.move"].search(
                expression.AND([
                    [("picking_type_id", "=", picking_type.id)],
                    domain,
                ])
            )

    @api.depends("weight_move_ids")
    def _compute_to_do_weights(self):
        for picking_type in self:
            picking_type.to_do_weights = len(picking_type.weight_move_ids)

    def action_weighing_operations(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sale_stock_weighing.weighing_operation_action"
        )
        action["name"] = _("%(name)s Weighing operations", name=self.name)
        action["domain"] = [("id", "in", self.weight_move_ids.ids)]
        action["context"] = dict(
            self.env.context,
            **ast.literal_eval(action.get("context", "{}") or "{}"),
            group_by=["picking_id"],
        )
        return action
