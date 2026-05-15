import ast

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    weighing_operations = fields.Boolean(
        related="picking_type_id.weighing_operations",
    )
    has_weighing_operations = fields.Boolean(
        compute="_compute_has_weighing_operations",
    )

    @api.depends("move_ids.has_weight")
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
        action["name"] = _("Operaciones de pesaje de %(name)s", name=self.name)
        action["domain"] = [("id", "in", weight_moves.ids)]
        action["context"] = dict(
            self.env.context,
            **ast.literal_eval(action.get("context", "{}") or "{}"),
            group_by=["picking_id"],
        )
        return action

    def _get_unweighed_moves(self):
        """Return moves that need weighing but haven't been fully weighed yet."""
        self.ensure_one()
        moves_to_weigh = self.move_ids.filtered("has_weight")
        return moves_to_weigh.filtered(
            lambda m: not m.move_line_ids
            or not all(m.move_line_ids.mapped("has_recorded_weight"))
        )

    def button_validate(self):
        for picking in self:
            unweighed = picking._get_unweighed_moves()
            if unweighed:
                raise UserError(
                    _(
                        "Las siguientes operaciones deben pesarse antes de validar %(picking)s:\n%(moves)s\n\n"
                        "Usá el asistente de pesaje para registrar los pesos.",
                        picking=picking.name,
                        moves="\n".join(
                            "- %s" % m.product_id.display_name for m in unweighed
                        ),
                    )
                )
        return super().button_validate()
