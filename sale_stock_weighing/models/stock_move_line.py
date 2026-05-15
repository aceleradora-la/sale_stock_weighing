from odoo import _, api, fields, models


class StockMoveLine(models.Model):
    _name = "stock.move.line"
    _inherit = ["stock.move.line", "weighing.mixin"]

    has_recorded_weight = fields.Boolean(
        string="Has Recorded Weight",
        help="The weight was set from the weighing wizard",
    )
    recorded_weight = fields.Float(
        string="Recorded Weight",
        digits="Product Unit of Measure",
        help="Actual weight recorded during weighing operation",
    )
    weighing_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Weighing User",
        readonly=True,
    )
    weighing_date = fields.Datetime(
        string="Weighing Date",
        readonly=True,
    )
    piece_price = fields.Float(
        string="Piece Price",
        compute="_compute_piece_price",
        digits="Product Price",
        help="Price of this piece: recorded weight × price per weight unit from the sale order.",
    )
    piece_price_currency_symbol = fields.Char(
        compute="_compute_piece_price",
        help="Currency symbol for the piece price.",
    )

    @api.depends(
        "recorded_weight",
        "move_id.sale_line_id.price_per_weight",
        "move_id.sale_line_id.order_id.currency_id",
    )
    def _compute_piece_price(self):
        for line in self:
            sale_line = line.move_id.sale_line_id
            if sale_line and sale_line.price_per_weight and line.recorded_weight:
                line.piece_price = line.recorded_weight * sale_line.price_per_weight
                line.piece_price_currency_symbol = (
                    sale_line.order_id.currency_id.symbol or ""
                )
            else:
                line.piece_price = 0.0
                line.piece_price_currency_symbol = ""

    def action_weighing(self):
        first = self[:1]
        if not first:
            return False
        first.move_id.action_lock_weighing_operation()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sale_stock_weighing.weighing_wizard_action"
        )
        action["name"] = first._get_action_weighing_name()
        action["context"] = dict(
            self.env.context,
            default_selected_move_line_id=first.id,
            default_weight=first.recorded_weight or first.quantity,
            default_move_line_ids=self.ids,
            default_print_label=first.move_id._get_default_print_label(),
            default_move_id=first.move_id.id,
        )
        return action

    def _get_action_weighing_name(self):
        self.ensure_one()
        name = _(
            "Weigh %(quantity)s %(uom)s of %(product)s",
            quantity=self.quantity,
            uom=self.product_uom_id.name,
            product=self.product_id.name,
        )
        if self.lot_id:
            name += " (%s)" % self.lot_id.name
        return name

    def action_print_weight_record_label(self):
        if not self:
            return False
        picking_type = self[:1].move_id.picking_type_id
        if picking_type.weighing_label_format == "zpl":
            report = self.env.ref(
                "sale_stock_weighing.action_report_weighing_label_zpl"
            )
        else:
            report = self.env.ref("sale_stock_weighing.action_report_weighing_label")
        return report.report_action(self)

    def action_reset_weights(self):
        self.write(
            {
                "recorded_weight": 0,
                "has_recorded_weight": False,
                "weighing_user_id": False,
                "weighing_date": False,
            }
        )
