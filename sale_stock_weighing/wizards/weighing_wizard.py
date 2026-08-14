from odoo import api, fields, models


class WeighingWizard(models.TransientModel):
    _name = "weighing.wizard"
    _description = "Registrar pesos en operaciones detalladas"

    move_id = fields.Many2one(comodel_name="stock.move")
    product_id = fields.Many2one(comodel_name="product.product", readonly=True)
    product_tracking = fields.Selection(
        selection=[
            ("none", "No Tracking"),
            ("lot", "By Lots"),
            ("serial", "Unique Serial Number"),
        ],
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
    weight_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        compute="_compute_weight_uom_id",
        string="UdM de Pesaje",
        help="Unidad de medida del peso — usada por el widget de balanza remota para la conversión de unidades.",
    )
    print_label = fields.Boolean(
        string="Imprimir Etiqueta",
        help="Imprimir la etiqueta al registrar el peso",
    )
    remaining_count = fields.Integer(
        compute="_compute_remaining_count",
    )

    @api.depends("move_id.product_id.weighing_uom_id")
    def _compute_weight_uom_id(self):
        for wiz in self:
            wiz.weight_uom_id = wiz.move_id.product_id.weighing_uom_id

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if not record.move_id:
                continue
            record.product_id = record.move_id.product_id
            record.product_tracking = record.move_id.product_id.tracking or "none"
            if not record.selected_move_line_id:
                unweighed = record.move_id.move_line_ids.filtered(
                    lambda l: not l.has_recorded_weight
                )
                if unweighed:
                    record.selected_move_line_id = unweighed[:1]
        return records

    @api.depends("product_id")
    def _compute_available_lot_ids(self):
        StockLot = self.env["stock.lot"]
        for wiz in self:
            if wiz.product_id.tracking == "none" or not wiz.product_id:
                wiz.available_lot_ids = False
                continue
            wiz.available_lot_ids = StockLot.search(
                [("product_id", "=", wiz.product_id.id)],
                order="create_date desc",
                limit=50,
            )

    @api.depends("move_id.move_line_ids.has_recorded_weight")
    def _compute_remaining_count(self):
        for wiz in self:
            wiz.remaining_count = len(
                wiz.move_id.move_line_ids.filtered(lambda l: not l.has_recorded_weight)
            )

    def record_weight(self):
        self.ensure_one()
        selected_line = self.selected_move_line_id
        if not selected_line:
            return {"type": "ir.actions.act_window_close"}
        if self.weight:
            vals = {
                "recorded_weight": self.weight,
                "has_recorded_weight": True,
                "weighing_user_id": self.env.user.id,
                "weighing_date": fields.Datetime.now(),
            }
            if self.lot_id:
                vals["lot_id"] = self.lot_id.id
            if selected_line.weight_is_quantity:
                # La cantidad y el peso son la misma magnitud: el peso pesado
                # pisa la cantidad de la línea (ej: recepción de 102 kg contra
                # una demanda de 100 kg).
                vals["quantity"] = selected_line._get_quantity_from_weight(self.weight)
        else:
            vals = {
                "recorded_weight": 0,
                "has_recorded_weight": False,
                "weighing_user_id": False,
                "weighing_date": False,
            }
        selected_line.write(vals)
        selected_line.move_id.action_unlock_weigh_operation()
        self.weight = 0.0
        if self.print_label:
            action = selected_line.action_print_weight_record_label()
            action["close_on_report_download"] = True
            return action
        return {"type": "ir.actions.act_window_close"}

    def action_close(self):
        move = self.move_id or self.selected_move_line_id.move_id
        if move:
            move.action_unlock_weigh_operation()

    def unlink(self):
        for wiz in self:
            move = wiz.move_id or wiz.selected_move_line_id.move_id
            if move:
                move.weighing_user_id = False
        return super().unlink()
