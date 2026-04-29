import ast

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools import float_compare


class StockMove(models.Model):
    _name = "stock.move"
    _inherit = ["stock.move", "weighing.mixin"]

    recorded_weight = fields.Float(
        string="Recorded Weight",
        compute="_compute_recorded_weight",
        digits="Product Unit of Measure",
    )
    move_lines_weighed = fields.Boolean(
        compute="_compute_recorded_weight",
    )
    weighing_state = fields.Selection(
        selection=[
            ("weighed", "Weighed"),
            ("weighing", "Weighing"),
            ("to_weigh", "To weigh"),
        ],
        compute="_compute_weighing_state",
        store=True,
    )
    weighing_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Weighing User",
        help="User currently weighing this operation. Locks the operation for others.",
    )
    is_weighing_operation_locked = fields.Boolean(
        compute="_compute_is_weighing_operation_locked",
    )
    lot_names = fields.Char(
        compute="_compute_lot_names",
    )
    origin_names = fields.Char(
        compute="_compute_origin_names",
    )
    weighing_label_report_id = fields.Many2one(
        comodel_name="ir.actions.report",
        related="picking_type_id.weighing_label_report_id",
    )
    show_weighing_print_button = fields.Boolean(
        compute="_compute_show_weighing_print_button",
    )
    self_move_ids = fields.Many2many(
        comodel_name="stock.move",
        compute="_compute_self_move_ids",
    )
    weighing_state_color = fields.Integer(
        compute="_compute_weighing_state_color",
    )
    qty_picked = fields.Float(
        string="Picked Quantity",
        compute="_compute_qty_picked",
        digits="Product Unit of Measure",
        store=True,
        readonly=False,
    )

    @api.depends("move_line_ids.qty_picked")
    def _compute_qty_picked(self):
        for move in self:
            move.qty_picked = sum(move.move_line_ids.mapped("qty_picked"))

    @api.depends("move_line_ids.recorded_weight")
    def _compute_recorded_weight(self):
        for move in self:
            move.recorded_weight = sum(move.move_line_ids.mapped("recorded_weight"))
            move.move_lines_weighed = bool(move.move_line_ids) and all(
                move.move_line_ids.mapped("has_recorded_weight")
            )

    @api.depends("move_line_ids.recorded_weight", "state", "product_id")
    def _compute_weighing_state(self):
        self.weighing_state = False
        for move in self.filtered("has_weight"):
            move_to_do = move.state not in {"draft", "cancel", "done"}
            if (
                move.move_lines_weighed
                or float_compare(
                    move.quantity,
                    move.product_uom_qty,
                    precision_rounding=move.product_uom.rounding,
                ) >= 0
            ) and any(move.move_line_ids.mapped("has_recorded_weight")):
                move.weighing_state = "weighed"
            elif move.recorded_weight and not move.move_lines_weighed and move_to_do:
                move.weighing_state = "weighing"
            elif (
                not move.recorded_weight
                and not move.move_lines_weighed
                and move_to_do
                and not move.qty_picked
            ):
                move.weighing_state = "to_weigh"

    @api.depends("move_line_ids.lot_id")
    def _compute_lot_names(self):
        self.lot_names = False
        for move in self:
            move.lot_names = ",".join(move.move_line_ids.lot_id.mapped("name"))

    @api.depends("move_line_ids.location_id")
    def _compute_origin_names(self):
        self.origin_names = False
        for move in self:
            move.origin_names = ",".join(move.move_line_ids.location_id.mapped("name"))

    @api.depends("weighing_user_id", "state")
    def _compute_is_weighing_operation_locked(self):
        self.is_weighing_operation_locked = False
        locked_moves = self.filtered(
            lambda x: x.state not in {"cancel", "draft", "done"}
            and x.weighing_user_id
            and x.weighing_user_id != self.env.user
        )
        locked_moves.is_weighing_operation_locked = True

    @api.depends("quantity", "picking_type_id.weighing_label_report_id")
    def _compute_show_weighing_print_button(self):
        self.show_weighing_print_button = False
        self.filtered(
            lambda x: x.quantity and x.picking_type_id.weighing_label_report_id
        ).show_weighing_print_button = True

    def _compute_weighing_state_color(self):
        state_map = {"weighed": 10, "to_weigh": 1, "weighing": 3}
        for move in self:
            move.weighing_state_color = state_map.get(move.weighing_state, 0)

    def _has_weigh_domain(self):
        domain = super()._has_weigh_domain()
        domain = expression.AND([domain, [("product_uom_qty", ">", 0)]])
        return domain

    def _search_has_weight(self, operator, value):
        domain = super()._search_has_weight(operator, value)
        domain = expression.AND([domain, [("product_uom_qty", ">", 0)]])
        return domain

    def action_lock_weighing_operation(self):
        self.ensure_one()
        if self.weighing_user_id and self.weighing_user_id != self.env.user:
            raise UserError(
                _("The user %(user)s is already weighing this operation", user=self.weighing_user_id.name)
            )
        self.weighing_user_id = self.env.user

    def action_unlock_weigh_operation(self):
        self.ensure_one()
        self.weighing_user_id = False

    def _get_default_print_label(self):
        return self.picking_type_id.print_weighing_label

    def action_weighing(self):
        self.action_lock_weighing_operation()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sale_stock_weighing.weighing_wizard_action"
        )
        action["name"] = fields.first(self.move_line_ids)._get_action_weighing_name()
        action["context"] = dict(
            self.env.context,
            default_selected_move_line_id=(fields.first(self.move_line_ids).id),
            default_weight=self.recorded_weight or self.quantity,
            default_move_line_ids=self.move_line_ids.ids,
            default_print_label=self._get_default_print_label(),
        )
        return action

    def action_add_move_line(self):
        action = self.action_weighing()
        action["context"].update(
            default_wizard_state="new_move_line",
            default_move_id=self.id,
            default_weight=0,
        )
        action["context"].pop("default_selected_move_line_id", None)
        action["name"] = _(
            "New operation for %(product)s (%(operation)s) "
            "%(remain).2f %(uom)s remaining",
            product=self.product_id.name,
            operation=self.reference,
            remain=max((self.product_uom_qty - self.quantity), 0),
            uom=self.product_uom.name,
        )
        return action

    def action_weight_detailed_operations(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sale_stock_weighing.weighing_operation_action"
        )
        action["display_name"] = _(
            "Detailed operations for %(name)s", name=self.name
        )
        action["domain"] = [("id", "=", self.id)]
        action["view_mode"] = "form"
        action["res_id"] = self.id
        action["views"] = [
            (view, mode) for view, mode in action["views"] if mode == "form"
        ]
        action["context"] = dict(
            self.env.context,
            **ast.literal_eval(action.get("context", "{}") or "{}"),
            weight_operation_details=True,
        )
        action["context"].pop("show_weight_detail_buttons", None)
        return action

    def action_print_weight_record_label(self):
        return self.move_line_ids.action_print_weight_record_label()

    def action_reset_weights(self):
        self.move_line_ids.action_reset_weights()

    def action_force_weighed(self):
        self.weighing_state = "weighed"
