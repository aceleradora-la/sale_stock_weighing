from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import clean_context


class WeighingWizard(models.TransientModel):
    _name = "weighing.wizard"
    _description = "Record weights over detailed operations"

    move_id = fields.Many2one(comodel_name="stock.move")
    product_id = fields.Many2one(
        comodel_name="product.product", related="move_id.product_id", store=True
    )
    available_lot_ids = fields.Many2many(
        comodel_name="stock.lot",
        compute="_compute_available_lot_ids",
    )
    lot_id = fields.Many2one(
        comodel_name="stock.lot",
        domain="[('id', 'in', available_lot_ids)]",
    )
    product_tracking = fields.Selection(
        related="product_id.tracking",
    )
    selected_move_line_id = fields.Many2one(
        comodel_name="stock.move.line",
    )
    weight = fields.Float(
        string="Weight",
        digits="Product Unit of Measure",
    )
    print_label = fields.Boolean(
        string="Print Label",
        help="Print label after recording the weight",
    )
    has_weight = fields.Boolean(
        compute="_compute_has_weight",
    )
    weighing_uom_name = fields.Char(
        compute="_compute_weighing_uom_name",
    )
    remaining_count = fields.Integer(
        compute="_compute_remaining_count",
    )

    @api.depends("product_id.weighing_uom_id")
    def _compute_weighing_uom_name(self):
        for wiz in self:
            wiz.weighing_uom_name = wiz.product_id.weighing_uom_id.name or "kg"

    @api.depends("move_id.move_line_ids.has_recorded_weight")
    def _compute_remaining_count(self):
        for wiz in self:
            wiz.remaining_count = len(
                wiz.move_id.move_line_ids.filtered(lambda l: not l.has_recorded_weight)
            )

    @api.depends("product_id")
    def _compute_available_lot_ids(self):
        self.available_lot_ids = False
        for wiz in self.filtered(lambda x: x.product_id.tracking != "none"):
            wiz.available_lot_ids = self.env["stock.lot"].search(
                [("product_id", "=", wiz.product_id.id)],
                order="create_date desc",
                limit=5,
            )
            default_lot_id = self.env.context.get("default_lot_id", False)
            if default_lot_id:
                wiz.available_lot_ids = wiz.available_lot_ids | self.env["stock.lot"].browse(default_lot_id)

    @api.depends("move_id", "selected_move_line_id")
    def _compute_has_weight(self):
        self.has_weight = False
        for wiz in self:
            wiz.has_weight = (
                wiz.move_id.has_weight or wiz.selected_move_line_id.has_weight
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.move_id and not record.selected_move_line_id:
                unweighed_lines = record.move_id.move_line_ids.filtered(
                    lambda l: not l.has_recorded_weight
                )
                if unweighed_lines:
                    record.selected_move_line_id = unweighed_lines[0]
        return records

    def _lot_creation_constraints(self):
        return [self.product_tracking != "none", not self.lot_id]

    def _check_lot_creation(self):
        self.ensure_one()
        if all(self._lot_creation_constraints()):
            raise UserError(_("You need to supply a Lot/Serial Number"))

    def record_weight(self):
        selected_line = self.selected_move_line_id
        if not selected_line:
            raise UserError(_("No move line selected"))
        if self.weight:
            selected_line.qty_picked = self.weight
            selected_line.recorded_weight = self.weight
            selected_line.has_recorded_weight = True
            selected_line.weighing_user_id = self.env.user
            selected_line.weighing_date = fields.Datetime.now()
        else:
            selected_line.qty_picked = 0
            selected_line.recorded_weight = 0
            selected_line.has_recorded_weight = False
            selected_line.weighing_user_id = False
            selected_line.weighing_date = False

        selected_line.move_id.action_unlock_weigh_operation()
        self.weight = 0.0
        if self.print_label:
            action = selected_line.action_print_weight_record_label()
            action["close_on_report_download"] = True
            return action
        return {"type": "ir.actions.act_window_close"}

    def action_close(self):
        (self.move_id or self.selected_move_line_id.move_id).action_unlock_weigh_operation()

    def unlink(self):
        (self.move_id | self.selected_move_line_id.move_id).weighing_user_id = False
        return super().unlink()
