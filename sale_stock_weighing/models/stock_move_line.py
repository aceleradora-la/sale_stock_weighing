from odoo import _, api, fields, models


class StockMoveLine(models.Model):
    _name = "stock.move.line"
    _inherit = ["stock.move.line", "weighing.mixin"]

    has_recorded_weight = fields.Boolean(
        string="Tiene Peso Registrado",
        help="El peso fue registrado desde el asistente de pesaje",
    )
    recorded_weight = fields.Float(
        string="Peso Registrado",
        digits="Product Unit of Measure",
        help="Peso real registrado durante la operación de pesaje",
    )
    weighing_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Usuario de Pesaje",
        readonly=True,
    )
    weighing_date = fields.Datetime(
        string="Fecha de Pesaje",
        readonly=True,
    )
    piece_price = fields.Float(
        string="Precio por Pieza",
        compute="_compute_piece_price",
        digits="Product Price",
        help="Precio de esta pieza: peso registrado × precio por unidad de peso del pedido de venta.",
    )
    piece_price_currency_symbol = fields.Char(
        compute="_compute_piece_price",
        help="Símbolo de moneda para el precio por pieza.",
    )
    weight_is_quantity = fields.Boolean(
        string="La cantidad ya expresa el peso",
        compute="_compute_weight_is_quantity",
        help="La UdM de la línea y la UdM de pesaje del producto son de la misma "
        "categoría, por lo que la cantidad ingresada ya expresa el peso real "
        "y no hace falta el asistente de pesaje.",
    )

    @api.depends("has_weight", "product_id.weighing_uom_id", "product_uom_id")
    def _compute_weight_is_quantity(self):
        for line in self:
            weighing_uom = line.product_id.weighing_uom_id
            line.weight_is_quantity = bool(
                line.has_weight
                and weighing_uom
                and line.product_uom_id
                and weighing_uom.category_id == line.product_uom_id.category_id
            )

    def _get_weight_from_quantity(self):
        """Convierte la cantidad de la línea a la UdM de pesaje del producto."""
        self.ensure_one()
        weighing_uom = self.product_id.weighing_uom_id
        if not weighing_uom or not self.product_uom_id:
            return 0.0
        if weighing_uom == self.product_uom_id:
            return self.quantity
        return self.product_uom_id._compute_quantity(self.quantity, weighing_uom)

    def _get_quantity_from_weight(self, weight):
        """Convierte un peso (en UdM de pesaje) a la UdM de la línea."""
        self.ensure_one()
        weighing_uom = self.product_id.weighing_uom_id
        if not weighing_uom or not self.product_uom_id:
            return weight
        if weighing_uom == self.product_uom_id:
            return weight
        return weighing_uom._compute_quantity(weight, self.product_uom_id)

    def _sync_weight_from_quantity(self):
        """Completa recorded_weight desde la cantidad para las líneas donde ambas
        magnitudes son la misma (UdM de pesaje y de la línea comparten categoría).

        Evita exigir el asistente de pesaje cuando el operario ya cargó el peso
        directamente en la cantidad — el caso típico de una recepción de
        mercadería que se compra y almacena en kg."""
        for line in self.filtered("weight_is_quantity"):
            line.write(
                {
                    "recorded_weight": line._get_weight_from_quantity(),
                    "has_recorded_weight": True,
                    "weighing_user_id": line.weighing_user_id.id or self.env.user.id,
                    "weighing_date": line.weighing_date or fields.Datetime.now(),
                }
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
            default_weight=first.recorded_weight or 0.0,
            default_move_line_ids=self.ids,
            default_print_label=first.move_id._get_default_print_label(),
            default_move_id=first.move_id.id,
        )
        return action

    def _get_action_weighing_name(self):
        self.ensure_one()
        name = _(
            "Pesar %(quantity)s %(uom)s de %(product)s",
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
