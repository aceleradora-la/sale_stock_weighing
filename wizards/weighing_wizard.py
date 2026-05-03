from odoo import _, api, fields, models


class WeighingWizard(models.TransientModel):
    _name = "weighing.wizard"
    _description = "Record weights over detailed operations"

    move_id = fields.Many2one(comodel_name="stock.move")
    product_id = fields.Many2one(comodel_name="product.product", readonly=True)
    product_tracking = fields.Selection(
        selection=[("none", "No Tracking"), ("lot", "By Lots"), ("serial", "Unique Serial Number")],
        readonly=True,
    )
    available_lot_ids = fields.Many2many(
        comodel_name="stock.lot",
        compute="_compute_available_lot_ids",
    )
    lot_id = fields.Many2one(
        comodel_name="stock.lot",
        domain="[('id', 'in', available_lot_ids)]",
    )
    selected_move_line_id = fields.Many2one(
        comodel_name="stock.move.line",
        readonly=True,
    )
    weight = fields.Float(
        string="Weight",
        digits="Product Unit of Measure",
    )
    print_label = fields.Boolean(
        string="Print Label",
        help="Print label after recording the weight",
    )
    remaining_count = fields.Integer(
        compute="_compute_remaining_count",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.move_id:
                record.product_id = record.move_id.product_id
                record.product_tracking = record.move_id.product_id.tracking or "none"
                if not record.selected_move_line_id:
                    unweighed = record.move_id.move_line_ids.filtered(
                        lambda l: not l.has_recorded_weight
                    )
                    if unweighed:
                        record.selected_move_line_id = unweighed[0]
        return records

    @api.depends("product_id")
    def _compute_available_lot_ids(self):
        self.available_lot_ids = False
        for wiz in self.filtered(lambda x: x.product_id.tracking != "none"):
            wiz.available_lot_ids = self.env["stock.lot"].search(
                [("product_id", "=", wiz.product_id.id)],
                order="create_date desc",
                limit=5,
            )

    @api.depends("move_id.move_line_ids.has_recorded_weight")
    def _compute_remaining_count(self):
        for wiz in self:
            wiz.remaining_count = len(
                wiz.move_id.move_line_ids.filtered(lambda l: not l.has_recorded_weight)
            )

    def record_weight(self):
        selected_line = self.selected_move_line_id
        if not selected_line:
            return {"type": "ir.actions.act_window_close"}
        vals = {}
        if self.weight:
            vals.update({
                "recorded_weight": self.weight,
                "has_recorded_weight": True,
                "weighing_user_id": self.env.user,
                "weighing_date": fields.Datetime.now(),
            })
            if self.lot_id:
                vals["lot_id"] = self.lot_id.id
        else:
            vals.update({
                "recorded_weight": 0,
                "has_recorded_weight": False,
                "weighing_user_id": False,
                "weighing_date": False,
            })
        selected_line.write(vals)

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
