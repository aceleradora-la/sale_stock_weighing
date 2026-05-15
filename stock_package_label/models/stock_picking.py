from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    number_of_packages = fields.Integer(
        string="Número de Bultos",
        compute="_compute_number_of_packages",
        store=True,
        readonly=False,
        help="Cantidad de bultos (cajas, bolsas, etc.) que componen este despacho.\n"
             "Se calcula automáticamente desde los paquetes de Odoo, "
             "pero puede ajustarse manualmente.",
    )
    package_label_weight = fields.Float(
        string="Peso para Etiqueta de Bulto",
        compute="_compute_package_label_weight",
        help="Peso de envío a mostrar en la etiqueta de bulto. "
             "Usa shipping_weight si está disponible (módulo stock_delivery), "
             "si no, weight_bulk, y si no, la suma de recorded_weight.",
    )
    package_label_weight_uom = fields.Char(
        string="UdM Peso Etiqueta",
        compute="_compute_package_label_weight",
    )

    @api.depends("move_line_ids.result_package_id")
    def _compute_number_of_packages(self):
        for picking in self:
            picking.number_of_packages = len(picking.move_line_ids.result_package_id)

    @api.depends(
        "move_line_ids.recorded_weight",
        "move_line_ids.has_recorded_weight",
    )
    def _compute_package_label_weight(self):
        """Determina el peso y la UdM a mostrar en la etiqueta de bulto,
        compatible con y sin el módulo stock_delivery instalado."""
        # Detectar campos disponibles una sola vez (nivel de clase, no de registro).
        has_shipping_weight = "shipping_weight" in self._fields
        has_weight_bulk = "weight_bulk" in self._fields
        has_weight_uom_name = "weight_uom_name" in self._fields

        for picking in self:
            # Peso: prioridad shipping_weight > weight_bulk > suma recorded_weight
            if has_shipping_weight and picking.shipping_weight:
                weight = picking.shipping_weight
            elif has_weight_bulk and picking.weight_bulk:
                weight = picking.weight_bulk
            else:
                weight = sum(
                    picking.move_line_ids
                    .filtered(lambda ml: ml.has_recorded_weight)
                    .mapped("recorded_weight")
                )
            picking.package_label_weight = weight

            # UdM
            if has_weight_uom_name and picking.weight_uom_name:
                picking.package_label_weight_uom = picking.weight_uom_name
            else:
                picking.package_label_weight_uom = "kg"

    def action_print_package_labels(self):
        """Imprime etiquetas de bultos en el formato configurado en el tipo de operación."""
        self.ensure_one()
        fmt = self.picking_type_id.package_label_format or "pdf"
        if fmt == "zpl":
            report = self.env.ref(
                "stock_package_label.action_report_package_label_zpl"
            )
        else:
            report = self.env.ref(
                "stock_package_label.action_report_package_label_pdf"
            )
        return report.report_action(self)
