import ast

from odoo import _, api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    weighing_operations = fields.Boolean(
        related="picking_type_id.weighing_operations",
    )
    has_weighing_operations = fields.Boolean(
        compute="_compute_has_weighing_operations",
    )

    @api.depends("move_ids")
    def _compute_has_weighing_operations(self):
        for picking in self:
            picking.has_weighing_operations = bool(
                picking.move_ids.filtered("has_weight")
            )

    def action_weighing_operations(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sale_stock_weighing.weighing_operation_action"
        )
        any_operation_actions = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sale_stock_weighing.any_operation_actions")
        )
        weight_moves = (
            self.move_ids
            if any_operation_actions
            else self.move_ids.filtered("has_weight")
        )
        action["name"] = _("Weighing operations for %(name)s", name=self.name)
        action["domain"] = [("id", "in", weight_moves.ids)]
        action["context"] = dict(
            self.env.context,
            **ast.literal_eval(action.get("context", "{}") or "{}"),
            group_by=["picking_id"],
        )
        return action

    def button_validate(self):
        for picking in self:
            moves_with_weight = picking.move_ids.filtered("has_weight")
            if not moves_with_weight:
                continue

            for move in moves_with_weight:
                weighed_lines = move.move_line_ids.filtered("has_recorded_weight")
                if not weighed_lines:
                    return {
                        "type": "ir.actions.act_window",
                        "name": _("Weighing Assistant"),
                        "res_model": "weighing.wizard",
                        "view_mode": "form",
                        "target": "new",
                        "context": {
                            "default_picking_id": picking.id,
                            "default_move_id": move.id,
                            "active_id": picking.id,
                            "active_model": "stock.picking",
                        },
                    }

        return super().button_validate()
