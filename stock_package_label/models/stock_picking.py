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
        has_shipping_weight = "shipping_weight" in self._fields
        has_weight_bulk = "weight_bulk" in self._fields
        has_weight_uom_name = "weight_uom_name" in self._fields

        for picking in self:
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
            picking.package_label_weight_uom = (
                picking.weight_uom_name if has_weight_uom_name and picking.weight_uom_name
                else "kg"
            )

    def action_print_package_labels(self):
        """Abre el wizard de configuración de etiquetas de bultos."""
        self.ensure_one()
        return {
            "name": "Imprimir Etiquetas de Bultos",
            "type": "ir.actions.act_window",
            "res_model": "stock.package.label.layout",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_picking_id": self.id,
                "default_label_format": (
                    self.picking_type_id.package_label_format or "pdf"
                ),
            },
        }

    def _get_package_label_pages(self, columns=2, rows_per_page=3):
        """Devuelve los datos de etiquetas agrupados en páginas para impresión PDF.

        Cada página es una lista de dicts con:
          - number  : número de bulto (1-based)
          - total   : total de bultos
          - package : stock.quant.package o False
        """
        self.ensure_one()
        total = self.number_of_packages
        pkgs = self.move_line_ids.result_package_id
        labels_per_page = max(1, columns * rows_per_page)

        all_labels = [
            {
                "number": n,
                "total": total,
                "package": pkgs[n - 1] if pkgs and n <= len(pkgs) else False,
            }
            for n in range(1, total + 1)
        ]

        return [
            all_labels[i: i + labels_per_page]
            for i in range(0, len(all_labels), labels_per_page)
        ]
