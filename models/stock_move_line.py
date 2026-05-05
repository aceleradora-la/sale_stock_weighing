from odoo import _, fields, models


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
