from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    number_of_packages = fields.Integer(
        string="Número de Bultos",
        default=0,
        help="Cantidad de bultos (cajas, bolsas, etc.) que componen este despacho.\n"
             "Se ingresa manualmente antes de imprimir las etiquetas.",
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
    package_label_barcode_ref = fields.Char(
        string="Referencia Código de Barras",
        compute="_compute_package_label_barcode_ref",
        help="Número usado en el código de barras de la etiqueta de bulto. "
             "Usa l10n_ar_delivery_guide_number si está disponible, si no picking.name.",
    )

    def _compute_package_label_barcode_ref(self):
        has_guide = "l10n_ar_delivery_guide_number" in self._fields
        for picking in self:
            picking.package_label_barcode_ref = (
                picking.l10n_ar_delivery_guide_number
                if has_guide and picking.l10n_ar_delivery_guide_number
                else picking.name
            )

    # No se declaran aquí recorded_weight ni has_recorded_weight: los aporta
    # sale_stock_weighing, que no es dependencia de este módulo, y Odoo valida
    # los @depends contra el registro al cargar (ValueError si el campo falta).
    # El campo no es almacenado, así que se recalcula en cada lectura.
    @api.depends("move_line_ids")
    def _compute_package_label_weight(self):
        """Determina el peso y la UdM a mostrar en la etiqueta de bulto,
        compatible con y sin los módulos stock_delivery y sale_stock_weighing."""
        has_shipping_weight = "shipping_weight" in self._fields
        has_weight_bulk = "weight_bulk" in self._fields
        has_weight_uom_name = "weight_uom_name" in self._fields
        has_recorded_weight = (
            "recorded_weight" in self.env["stock.move.line"]._fields
        )

        for picking in self:
            if has_shipping_weight and picking.shipping_weight:
                weight = picking.shipping_weight
            elif has_weight_bulk and picking.weight_bulk:
                weight = picking.weight_bulk
            elif has_recorded_weight:
                weight = sum(
                    picking.move_line_ids
                    .filtered(lambda ml: ml.has_recorded_weight)
                    .mapped("recorded_weight")
                )
            else:
                weight = 0.0
            picking.package_label_weight = weight
            picking.package_label_weight_uom = (
                picking.weight_uom_name if has_weight_uom_name and picking.weight_uom_name
                else "kg"
            )

    def get_package_label_pages(self, columns=2, rows_per_page=3):
        """Agrupa las etiquetas en páginas y filas para el reporte PDF.

        Retorna lista de páginas; cada página es una lista de filas;
        cada fila es una lista de dicts {'number': N, 'total': T}.

        Ejemplo con 5 bultos, columns=2, rows_per_page=2:
          Página 1: [[lbl1, lbl2], [lbl3, lbl4]]
          Página 2: [[lbl5]]
        """
        self.ensure_one()
        total = self.number_of_packages
        columns = max(1, int(columns))
        rows_per_page = max(1, int(rows_per_page))
        labels_per_page = columns * rows_per_page

        all_labels = [{"number": n, "total": total} for n in range(1, total + 1)]

        pages = []
        for page_start in range(0, len(all_labels), labels_per_page):
            page_labels = all_labels[page_start: page_start + labels_per_page]
            rows = []
            for row_start in range(0, len(page_labels), columns):
                rows.append(page_labels[row_start: row_start + columns])
            pages.append(rows)
        return pages

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

