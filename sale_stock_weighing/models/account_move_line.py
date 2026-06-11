from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    recorded_weight = fields.Float(
        string="Peso Registrado",
        digits="Product Unit of Measure",
        help="Peso real entregado y facturado.",
    )
    weight_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="UdM de Pesaje",
        help="Unidad de medida del peso registrado.",
    )
    weight_uom_name = fields.Char(
        string="Nombre UdM de Pesaje",
        related="weight_uom_id.name",
    )
    x_delivered_piece_count = fields.Integer(
        string="Piezas Entregadas",
        help="Cantidad de piezas (unidades) entregadas, para mostrar en la factura.",
    )

    def _compute_product_uom_qty(self):
        """Para productos pesables, muestra el conteo de piezas entregadas en lugar
        de la conversión automática kg→UdM nativa (que puede dar valores erróneos
        cuando las UdM pertenecen a categorías distintas, ej: 3.45 kg → 3450 Unidades
        si Unidades tiene factor 0.001 respecto al kg)."""
        super()._compute_product_uom_qty()
        for line in self:
            sol = line.sale_line_ids[:1]
            if (
                sol
                and sol.product_id.is_weighed_product
                and sol.delivered_piece_count
            ):
                line.product_uom_qty = float(sol.delivered_piece_count)


class AccountMove(models.Model):
    _inherit = "account.move"

    company_use_stock_weighing = fields.Boolean(
        related="company_id.use_stock_weighing",
        store=False,
    )

    def action_recompute_weight_lines(self):
        for invoice in self:
            if invoice.state != "draft":
                continue
            for inv_line in invoice.invoice_line_ids:
                sol = inv_line.sale_line_ids[:1]
                if (
                    sol
                    and sol.product_id.is_weighed_product
                    and sol.total_delivered_weight > 0
                ):
                    inv_line.write(sol._get_weighed_invoice_vals(name=inv_line.name))
