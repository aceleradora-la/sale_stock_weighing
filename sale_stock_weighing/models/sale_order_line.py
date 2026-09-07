import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    price_per_weight = fields.Float(
        string="Precio / Unidad de Peso",
        digits="Product Price",
        help="Precio por unidad de peso (ej: por kg). "
        "Se usa cuando el producto se vende por unidades pero se factura por peso.",
    )
    x_piece_count = fields.Integer(
        string="Piezas",
        help="Cantidad de piezas (unidades) a entregar. "
        "Informativo — aparece en los reportes junto al peso.",
    )
    total_planned_weight = fields.Float(
        string="Peso Estimado",
        compute="_compute_total_planned_weight",
        digits="Product Unit of Measure",
        help="Peso total planificado según la cantidad del pedido y el peso estándar por unidad.",
    )
    total_delivered_weight = fields.Float(
        string="Peso Entregado",
        compute="_compute_total_delivered_weight",
        digits="Product Unit of Measure",
        store=True,
        help="Peso total real entregado desde los movimientos de stock.",
    )
    delivered_piece_count = fields.Integer(
        string="Piezas Entregadas",
        compute="_compute_delivered_piece_count",
        store=True,
        help="Cantidad de piezas entregadas, determinado por los lotes distintos en movimientos realizados. "
        "Si no hay seguimiento por lotes, cuenta las líneas de movimiento pesadas.",
    )

    @api.depends(
        "product_id.weighing_uom_id",
        "product_id.weight",
        "product_uom_qty",
    )
    def _compute_total_planned_weight(self):
        # product.weight en Odoo siempre está expresado en kg, sin importar la
        # UdM de venta del producto. La conversión correcta es de kg → weighing_uom,
        # no de product.uom_id → weighing_uom (que son categorías incompatibles).
        kg_uom = self.env.ref("uom.product_uom_kgm")
        for line in self:
            line.total_planned_weight = 0.0
            product = line.product_id
            if not product.weighing_uom_id:
                continue
            standard_weight = product.weight or 0.0
            weighing_uom = product.weighing_uom_id
            if weighing_uom and weighing_uom != kg_uom:
                try:
                    standard_weight = kg_uom._compute_quantity(
                        product.weight, weighing_uom
                    )
                except Exception:
                    _logger.debug(
                        "Product %s: no se pudo convertir product.weight de kg a %s; "
                        "se usa el valor en kg sin conversión.",
                        product.display_name,
                        weighing_uom.name,
                    )
            line.total_planned_weight = line.product_uom_qty * standard_weight

    @api.depends(
        "move_ids.move_line_ids.recorded_weight",
        "move_ids.move_line_ids.has_recorded_weight",
        "move_ids.move_line_ids.quantity",
        "move_ids.state",
    )
    def _compute_total_delivered_weight(self):
        # _weighing_relevant descarta las líneas en cantidad cero: si se decidió
        # no entregar algo, su peso no se factura aunque haya quedado registrado.
        for line in self:
            line.total_delivered_weight = sum(
                line.move_ids.move_line_ids._weighing_relevant()
                .filtered("has_recorded_weight")
                .mapped("recorded_weight")
            )

    @api.depends(
        "move_ids.state",
        "move_ids.move_line_ids.lot_id",
        "move_ids.move_line_ids.has_recorded_weight",
        "move_ids.move_line_ids.quantity",
    )
    def _compute_delivered_piece_count(self):
        for line in self:
            if not line.product_id.is_weighed_product:
                line.delivered_piece_count = 0
                continue
            done_moves = line.move_ids.filtered(lambda m: m.state == "done")
            weighed_lines = done_moves.move_line_ids._weighing_relevant().filtered(
                "has_recorded_weight"
            )
            # Prefer counting distinct lots (= physical pieces).
            # When lot tracking is off, sum the quantities on the weighed lines
            # (quantity is in pieces since we no longer sync it with recorded_weight).
            lots = weighed_lines.filtered("lot_id").lot_id
            if lots:
                line.delivered_piece_count = len(lots)
            else:
                line.delivered_piece_count = int(sum(weighed_lines.mapped("quantity")))

    def _get_weighed_invoice_vals(self, name=None, cumulative=False):
        """Return values to write on an account.move.line for a weighed product.

        Uses delta (incremental) quantities by default to avoid double-billing
        when deliveries are split across multiple batches.  Pass cumulative=True
        when rewriting an existing invoice line (e.g. action_recompute_weight_lines)
        so the line reflects the full delivered total instead of the delta.
        """
        self.ensure_one()
        product = self.product_id

        if cumulative:
            weight_to_invoice = self.total_delivered_weight
            pieces_to_invoice = self.delivered_piece_count
        else:
            # Subtract already-invoiced weight/pieces to get the incremental amount.
            existing_lines = self.invoice_lines.filtered(
                lambda l: l.move_id.state != "cancel"
                and l.move_id.move_type == "out_invoice"
            )
            weight_already_invoiced = sum(existing_lines.mapped("recorded_weight"))
            pieces_already_invoiced = sum(
                l.x_delivered_piece_count or 0 for l in existing_lines
            )
            weight_to_invoice = max(
                0.0, self.total_delivered_weight - weight_already_invoiced
            )
            pieces_to_invoice = max(
                0, self.delivered_piece_count - pieces_already_invoiced
            )

        raw_name = name if name is not None else self.name or ""
        base_name = raw_name.split("\n")[0]

        vals = {
            "quantity": weight_to_invoice,
            "price_unit": self.price_per_weight,
            "product_uom_id": product.weighing_uom_id.id,
            "recorded_weight": weight_to_invoice,
            "weight_uom_id": product.weighing_uom_id.id,
            "x_delivered_piece_count": pieces_to_invoice,
            "name": base_name,
        }

        AML = self.env["account.move.line"]
        if "product_uom_qty" in AML._fields:
            vals["product_uom_qty"] = float(pieces_to_invoice)

        return vals

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        if self.product_id.is_weighed_product and self.total_delivered_weight > 0:
            res.update(self._get_weighed_invoice_vals(name=res.get("name")))
        return res

    def _recompute_invoice_lines_for_weight(self):
        self.ensure_one()
        if not self.product_id.is_weighed_product:
            return
        invoices = self.invoice_lines.move_id.filtered(
            lambda m: m.move_type == "out_invoice" and m.state == "draft"
        )
        for invoice in invoices:
            for inv_line in invoice.invoice_line_ids.filtered(
                lambda l: l.product_id == self.product_id
            ):
                inv_line.write(self._get_weighed_invoice_vals(name=inv_line.name, cumulative=True))

    def _get_price_per_weight_from_pricelist(self):
        self.ensure_one()
        if not self.product_id.is_weighed_product:
            return 0.0
        pricelist = self.order_id.pricelist_id
        if not pricelist:
            return 0.0
        result = pricelist._get_matched_weighing_items(
            self.product_id, date=self.order_id.date_order
        )
        if result:
            return result[0].compute_price_per_weight(self.product_id, 1.0)
        return 0.0

    def _weighed_qty_in_pieces(self):
        """Si la cantidad facturada debe contarse en piezas en lugar de convertir.

        Solo aplica cuando la UdM de venta y la de pesaje son magnitudes
        distintas (ej: se vende por Unidades y se factura por kg): ahí la
        conversión de Odoo cruza categorías incompatibles y multiplica por el
        factor equivocado.

        Si son compatibles —el producto se vende y se pesa en kg— la conversión
        estándar es correcta y contar piezas daría de menos, porque
        delivered_piece_count trunca los kilos a entero.
        """
        self.ensure_one()
        product = self.product_id
        if not product.is_weighed_product or not product.weighing_uom_id:
            return False
        if not self.product_uom_id:
            return False
        return not product.weighing_uom_id._has_common_reference(self.product_uom_id)

    @api.depends("invoice_lines.x_delivered_piece_count", "invoice_lines.move_id.state")
    def _compute_qty_invoiced(self):
        super()._compute_qty_invoiced()
        for line in self:
            if not line._weighed_qty_in_pieces():
                continue
            qty = 0.0
            for inv_line in line.invoice_lines:
                if inv_line.move_id.state == "cancel":
                    continue
                pieces = inv_line.x_delivered_piece_count or 0
                if inv_line.move_id.move_type == "out_invoice":
                    qty += pieces
                elif inv_line.move_id.move_type == "out_refund":
                    qty -= pieces
            line.qty_invoiced = qty

    @api.onchange("product_id")
    def _onchange_product_id_weighing(self):
        if not self.product_id.is_weighed_product:
            return
        price_per_weight = self._get_price_per_weight_from_pricelist()
        weight = self.product_id.weight or 0.0
        if price_per_weight:
            self.price_per_weight = price_per_weight
            # price_unit = precio por UNIDAD = precio/kg × peso del producto
            self.price_unit = price_per_weight * weight if weight else price_per_weight
        elif weight:
            # Sin precio por peso en la lista, el unitario lo fija Odoo: se
            # deriva el $/kg dividiendo por el peso, que es la inversa exacta
            # del cálculo de arriba. Igualarlo al precio unitario daría un $/kg
            # inflado por el peso del producto y ensuciaría la factura.
            self.price_per_weight = self.price_unit / weight
        else:
            self.price_per_weight = self.price_unit
        self.product_uom_id = self.product_id.uom_id
        # Sincronizar piezas con la cantidad al elegir el producto
        if not self.x_piece_count:
            self.x_piece_count = int(self.product_uom_qty)

    @api.onchange("price_per_weight")
    def _onchange_price_per_weight_weighing(self):
        """Recalcula price_unit cuando el usuario edita el precio por peso en la SOL."""
        if not self.product_id.is_weighed_product or not self.price_per_weight:
            return
        weight = self.product_id.weight or 0.0
        self.price_unit = self.price_per_weight * weight if weight else self.price_per_weight

    @api.onchange("product_uom_qty")
    def _onchange_product_uom_qty_weighing(self):
        """Sincroniza x_piece_count con la cantidad cuando el producto se vende por peso."""
        if self.product_id.is_weighed_product:
            self.x_piece_count = int(self.product_uom_qty)
