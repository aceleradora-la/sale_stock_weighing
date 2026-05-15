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

    @api.depends(
        "move_line_ids.result_package_id",
        "package_level_ids",
    )
    def _compute_number_of_packages(self):
        for picking in self:
            # Contar paquetes destino (resultado de la operación).
            pkg_count = len(picking.move_line_ids.result_package_id)
            if not pkg_count:
                # Fallback: paquetes de origen movidos en bloque.
                pkg_count = len(picking.package_level_ids)
            picking.number_of_packages = pkg_count

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

    def _get_package_label_lines(self):
        """Devuelve una lista de dicts con los datos de cada etiqueta de bulto.

        Cada elemento representa un bulto con su número secuencial, el total
        y la referencia al paquete de Odoo (si existe).
        """
        self.ensure_one()
        total = self.number_of_packages
        packages = self.move_line_ids.result_package_id
        lines = []
        for n in range(1, total + 1):
            pkg = packages[n - 1] if packages and n <= len(packages) else False
            lines.append({
                "number": n,
                "total": total,
                "package": pkg,
            })
        return lines
