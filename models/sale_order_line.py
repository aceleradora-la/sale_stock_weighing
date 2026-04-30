from odoo import api, fields, models


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

    @api.depends("move_ids.move_line_ids.qty_picked", "move_ids.state")
    def _compute_total_delivered_weight(self):
        for line in self:
            if line.move_ids:
                line.total_delivered_weight = sum(
                    line.move_ids.move_line_ids.filtered("has_recorded_weight").mapped(
                        "qty_picked"
                    )
                )
            else:
                line.total_delivered_weight = 0.0

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        if self.product_id.is_weighed_product and self.total_delivered_weight > 0:
            res["quantity"] = self.total_delivered_weight
            res["price_unit"] = self.price_per_weight
            res["name"] = "%s\n[%s] %s x %s %s" % (
                self.name or "",
                self.product_id.default_code or "",
                self.product_id.display_name,
                self.total_delivered_weight,
                self.product_id.weighing_uom_id.name,
            )
        return res

    @api.onchange("product_id")
    def _onchange_product_id_weighing(self):
        if self.product_id.is_weighed_product:
            self.price_per_weight = self.price_unit
            self.product_uom_id = self.product_id.uom_id
