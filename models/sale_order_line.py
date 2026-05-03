from odoo import _, api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    price_per_weight = fields.Float(
        string="Price per Weight Unit",
        digits="Product Price",
        help="Price per weight unit (e.g. per kg). "
        "Used when the product is sold by units but invoiced by weight.",
    )
    total_planned_weight = fields.Float(
        string="Total Planned Weight",
        compute="_compute_total_planned_weight",
        digits="Product Unit of Measure",
        help="Planned total weight based on order quantity and standard weight.",
    )
    total_delivered_weight = fields.Float(
        string="Total Delivered Weight",
        compute="_compute_total_delivered_weight",
        digits="Product Unit of Measure",
        store=True,
        help="Actual total weight delivered from stock moves.",
    )

    @api.depends("product_id.weighing_uom_id", "product_uom_qty")
    def _compute_total_planned_weight(self):
        for line in self:
            if line.product_id.weighing_uom_id:
                standard_weight = line.product_id.weight or 0.0
                if line.product_id.uom_id != line.product_id.weighing_uom_id:
                    standard_weight = line.product_id.uom_id._compute_quantity(
                        line.product_id.weight, line.product_id.weighing_uom_id
                    )
                line.total_planned_weight = line.product_uom_qty * standard_weight
            else:
                line.total_planned_weight = 0.0

    @api.depends("move_ids.move_line_ids.recorded_weight", "move_ids.state")
    def _compute_total_delivered_weight(self):
        for line in self:
            if line.move_ids:
                line.total_delivered_weight = sum(
                    line.move_ids.move_line_ids.filtered("has_recorded_weight").mapped(
                        "recorded_weight"
                    )
                )
            else:
                line.total_delivered_weight = 0.0

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        if self.product_id.is_weighed_product and self.total_delivered_weight > 0:
            res["quantity"] = self.total_delivered_weight
            res["price_unit"] = self.price_per_weight
            res["product_uom_id"] = self.product_id.weighing_uom_id.id
            res["recorded_weight"] = self.total_delivered_weight
            res["weight_uom_id"] = self.product_id.weighing_uom_id.id
            res["name"] = "%s\n[%s] %s x %s %s" % (
                self.name or "",
                self.product_id.default_code or "",
                self.product_id.display_name,
                self.total_delivered_weight,
                self.product_id.weighing_uom_id.name,
            )
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
                inv_line.write({
                    "quantity": self.total_delivered_weight,
                    "price_unit": self.price_per_weight,
                    "product_uom_id": self.product_id.weighing_uom_id.id,
                    "recorded_weight": self.total_delivered_weight,
                    "weight_uom_id": self.product_id.weighing_uom_id.id,
                    "name": "%s\n[%s] %s x %s %s" % (
                        inv_line.name or "",
                        self.product_id.default_code or "",
                        self.product_id.display_name,
                        self.total_delivered_weight,
                        self.product_id.weighing_uom_id.name,
                    ),
                })

    def _get_price_per_weight_from_pricelist(self):
        self.ensure_one()
        if not self.product_id.is_weighed_product:
            return 0.0
        pricelist = self.order_id.pricelist_id
        result = pricelist._get_matched_weighing_items(self.product_id)
        if result:
            return result[0].compute_price_per_weight(self.product_id, 1.0)
        return 0.0

    @api.onchange("product_id")
    def _onchange_product_id_weighing(self):
        if self.product_id.is_weighed_product:
            price_from_pricelist = self._get_price_per_weight_from_pricelist()
            if price_from_pricelist:
                self.price_per_weight = price_from_pricelist
                self.price_unit = price_from_pricelist
            else:
                self.price_per_weight = self.price_unit
            self.product_uom_id = self.product_id.uom_id
