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
        string="Est. Weight",
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
        "product_id.uom_id",
        "product_uom_qty",
    )
    def _compute_total_planned_weight(self):
        for line in self:
            line.total_planned_weight = 0.0
            product = line.product_id
            if not product.weighing_uom_id:
                continue
            standard_weight = product.weight or 0.0
            uom = product.uom_id
            weighing_uom = product.weighing_uom_id
            if uom and uom != weighing_uom:
                try:
                    # _compute_quantity raises UserError if UoMs are incompatible
                    standard_weight = uom._compute_quantity(
                        product.weight, weighing_uom
                    )
                except Exception:
                    _logger.debug(
                        "Product %s: UoM %s y UdM de pesaje %s son incompatibles; "
                        "se usa product.weight sin conversión.",
                        product.display_name,
                        uom.name,
                        weighing_uom.name,
                    )
            line.total_planned_weight = line.product_uom_qty * standard_weight

    @api.depends(
        "move_ids.move_line_ids.recorded_weight",
        "move_ids.move_line_ids.has_recorded_weight",
        "move_ids.state",
    )
    def _compute_total_delivered_weight(self):
        for line in self:
            line.total_delivered_weight = sum(
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
    def _compute_delivered_piece_count(self):
        for line in self:
            if not line.product_id.is_weighed_product:
                line.delivered_piece_count = 0
                continue
            done_moves = line.move_ids.filtered(lambda m: m.state == "done")
            weighed_lines = done_moves.move_line_ids.filtered("has_recorded_weight")
            # Prefer counting distinct lots (= physical pieces).
            # When lot tracking is off, sum the quantities on the weighed lines
            # (quantity is in pieces since we no longer sync it with recorded_weight).
            lots = weighed_lines.filtered("lot_id").lot_id
            if lots:
                line.delivered_piece_count = len(lots)
            else:
                line.delivered_piece_count = int(sum(weighed_lines.mapped("quantity")))

    def _get_weighed_invoice_vals(self, name=None):
        """Return values to write on an account.move.line for a weighed product."""
        self.ensure_one()
        product = self.product_id
        base_name = name if name is not None else self.name or ""
        piece_info = ""
        if self.delivered_piece_count:
            uom_name = (self.product_uom_id or product.uom_id).name or "u"
            piece_info = " (%d %s)" % (self.delivered_piece_count, uom_name)
        # base_name ya incluye la referencia y nombre del producto (ej: "[103] Bondiola A/V").
        # Solo agregamos la info de piezas y el peso entregado, sin repetir el producto.
        return {
            "quantity": self.total_delivered_weight,
            "price_unit": self.price_per_weight,
            "product_uom_id": product.weighing_uom_id.id,
            "recorded_weight": self.total_delivered_weight,
            "weight_uom_id": product.weighing_uom_id.id,
            "x_delivered_piece_count": self.delivered_piece_count,
            "name": "%s%s\nEntregado: %s %s" % (
                base_name,
                piece_info,
                self.total_delivered_weight,
                product.weighing_uom_id.name,
            ),
        }

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
                inv_line.write(self._get_weighed_invoice_vals(name=inv_line.name))

    def _get_price_per_weight_from_pricelist(self):
        self.ensure_one()
        if not self.product_id.is_weighed_product:
            return 0.0
        pricelist = self.order_id.pricelist_id
        if not pricelist:
            return 0.0
        result = pricelist._get_matched_weighing_items(self.product_id)
        if result:
            return result[0].compute_price_per_weight(self.product_id, 1.0)
        return 0.0

    @api.onchange("product_id")
    def _onchange_product_id_weighing(self):
        if not self.product_id.is_weighed_product:
            return
        price_from_pricelist = self._get_price_per_weight_from_pricelist()
        if price_from_pricelist:
            self.price_per_weight = price_from_pricelist
            self.price_unit = price_from_pricelist
        else:
            self.price_per_weight = self.price_unit
        self.product_uom_id = self.product_id.uom_id
