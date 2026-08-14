from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    company_use_stock_weighing = fields.Boolean(
        related="company_id.use_stock_weighing",
        string="Empresa usa pesaje",
        store=False,  # no columna en DB — computed vía ir.config_parameter
    )


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    price_per_weight = fields.Float(
        string="Precio / Unidad de Peso",
        digits="Product Price",
        help="Precio por unidad de peso (ej: por kg) acordado con el proveedor. "
        "Se usa cuando el producto se compra por unidades pero se factura por peso.",
    )
    total_received_weight = fields.Float(
        string="Peso Recibido",
        compute="_compute_total_received_weight",
        digits="Product Unit of Measure",
        store=True,
        help="Peso total real recibido desde los movimientos de stock.",
    )
    received_piece_count = fields.Integer(
        string="Piezas Recibidas",
        compute="_compute_received_piece_count",
        store=True,
        help="Cantidad de piezas recibidas, determinada por los lotes distintos en "
        "movimientos realizados. Si no hay seguimiento por lotes, cuenta las "
        "líneas de movimiento pesadas.",
    )

    @api.depends(
        "move_ids.move_line_ids.recorded_weight",
        "move_ids.move_line_ids.has_recorded_weight",
        "move_ids.state",
    )
    def _compute_total_received_weight(self):
        for line in self:
            line.total_received_weight = sum(
                line.move_ids.move_line_ids
                .filtered("has_recorded_weight")
                .mapped("recorded_weight")
            )

    @api.depends(
        "move_ids.state",
        "move_ids.move_line_ids.lot_id",
        "move_ids.move_line_ids.has_recorded_weight",
        "move_ids.move_line_ids.quantity",
    )
    def _compute_received_piece_count(self):
        for line in self:
            if not line.product_id.is_weighed_product:
                line.received_piece_count = 0
                continue
            done_moves = line.move_ids.filtered(lambda m: m.state == "done")
            weighed_lines = done_moves.move_line_ids.filtered("has_recorded_weight")
            lots = weighed_lines.filtered("lot_id").lot_id
            if lots:
                line.received_piece_count = len(lots)
            else:
                line.received_piece_count = int(sum(weighed_lines.mapped("quantity")))

    def _weighed_purchase_applies(self):
        """La lógica de facturación por peso solo aplica cuando la UdM de compra
        y la de pesaje son magnitudes distintas.

        Si comparten categoría (ej: se compra y se pesa en kg) la cantidad ya
        expresa el peso y la facturación estándar de Odoo es correcta."""
        self.ensure_one()
        product = self.product_id
        if not product.is_weighed_product or not product.weighing_uom_id:
            return False
        if not self.product_uom_id:
            return False
        return product.weighing_uom_id.category_id != self.product_uom_id.category_id

    def _get_weighed_bill_vals(self, cumulative=False):
        """Valores para la línea de factura de proveedor de un producto pesable.

        Usa cantidades incrementales (delta) por defecto para no facturar dos
        veces cuando la recepción se hace en varias tandas."""
        self.ensure_one()
        product = self.product_id

        if cumulative:
            weight_to_invoice = self.total_received_weight
            pieces_to_invoice = self.received_piece_count
        else:
            existing_lines = self.invoice_lines.filtered(
                lambda l: l.move_id.state != "cancel"
                and l.move_id.move_type == "in_invoice"
            )
            weight_already_invoiced = sum(existing_lines.mapped("recorded_weight"))
            pieces_already_invoiced = sum(
                l.x_delivered_piece_count or 0 for l in existing_lines
            )
            weight_to_invoice = max(
                0.0, self.total_received_weight - weight_already_invoiced
            )
            pieces_to_invoice = max(
                0, self.received_piece_count - pieces_already_invoiced
            )

        vals = {
            "quantity": weight_to_invoice,
            "price_unit": self.price_per_weight,
            "product_uom_id": product.weighing_uom_id.id,
            "recorded_weight": weight_to_invoice,
            "weight_uom_id": product.weighing_uom_id.id,
            "x_delivered_piece_count": pieces_to_invoice,
        }

        AML = self.env["account.move.line"]
        if "product_uom_qty" in AML._fields:
            vals["product_uom_qty"] = float(pieces_to_invoice)

        return vals

    def _prepare_account_move_line(self, move=False):
        res = super()._prepare_account_move_line(move=move)
        if self._weighed_purchase_applies() and self.total_received_weight > 0:
            res.update(self._get_weighed_bill_vals())
        return res

    @api.depends("invoice_lines.x_delivered_piece_count", "invoice_lines.move_id.state")
    def _compute_qty_invoiced(self):
        """Para productos pesables facturados por peso, la cantidad facturada se
        cuenta en piezas y no convirtiendo kg a la UdM de compra (conversión que
        cruza categorías incompatibles y multiplica por el factor equivocado)."""
        super()._compute_qty_invoiced()
        for line in self:
            if not line._weighed_purchase_applies():
                continue
            qty = 0.0
            for inv_line in line.invoice_lines:
                if inv_line.move_id.state == "cancel":
                    continue
                pieces = inv_line.x_delivered_piece_count or 0
                if inv_line.move_id.move_type == "in_invoice":
                    qty += pieces
                elif inv_line.move_id.move_type == "in_refund":
                    qty -= pieces
            line.qty_invoiced = qty

    @api.onchange("price_per_weight")
    def _onchange_price_per_weight_purchase(self):
        """price_unit = precio por UNIDAD = precio/kg × peso del producto."""
        if not self._weighed_purchase_applies() or not self.price_per_weight:
            return
        weight = self.product_id.weight or 0.0
        self.price_unit = (
            self.price_per_weight * weight if weight else self.price_per_weight
        )
