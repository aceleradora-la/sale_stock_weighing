import json
from urllib.parse import quote

from odoo import api, fields, models


class PackageLabelLayout(models.TransientModel):
    """Wizard para configurar e imprimir etiquetas de bultos.

    Para PDF: permite elegir columnas y filas por hoja.
    Para ZPL: delega en el módulo IoT de Odoo el ruteo a la impresora.
              Si el reporte tiene una impresora configurada en
              IoT → Dispositivos → Informes de la impresora, imprime directo.
              Si no, Odoo muestra el selector de impresoras.
    """

    _name = "stock.package.label.layout"
    _description = "Configuración de Etiquetas de Bultos"

    picking_id = fields.Many2one(
        comodel_name="stock.picking",
        string="Remito",
        required=True,
        readonly=True,
    )
    number_of_packages = fields.Integer(
        related="picking_id.number_of_packages",
        string="Bultos a imprimir",
    )
    label_format = fields.Selection(
        selection=[("pdf", "PDF (hoja)"), ("zpl", "ZPL (Zebra)")],
        string="Formato",
        required=True,
        default="pdf",
    )
    # ── Opciones PDF ────────────────────────────────────────────────
    columns = fields.Integer(
        string="Columnas por hoja",
        default=2,
        help="Cantidad de etiquetas por fila.\n"
             "1 → una etiqueta grande por hoja\n"
             "2 → dos por fila  (recomendado A4)\n"
             "3 → tres por fila",
    )
    rows_per_page = fields.Integer(
        string="Filas por hoja",
        default=3,
        help="Filas de etiquetas por página A4.\n"
             "Con 2 columnas × 3 filas → 6 etiquetas por hoja.",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        picking_id = self.env.context.get("default_picking_id")
        if picking_id:
            picking = self.env["stock.picking"].browse(picking_id)
            res["label_format"] = picking.picking_type_id.package_label_format or "pdf"
        return res

    def action_print(self):
        """Genera o envía las etiquetas según el formato elegido."""
        self.ensure_one()
        picking = self.picking_id

        if self.label_format == "zpl":
            # El módulo IoT intercepta report_action automáticamente:
            # - Si hay impresora configurada en IoT → imprime directo.
            # - Si no → muestra el selector de impresoras en el navegador.
            report = self.env.ref(
                "stock_package_label.action_report_package_label_zpl"
            )
            return report.report_action(picking)

        # PDF: construimos la URL directamente para asegurar que el ID
        # del picking llegue al template. report_action() en Odoo 19
        # no propaga los IDs correctamente cuando se invoca desde un
        # dialog TransientModel (docs queda vacío).
        options = quote(json.dumps({
            "columns": max(1, self.columns),
            "rows_per_page": max(1, self.rows_per_page),
        }))
        url = "/report/pdf/stock_package_label.report_package_label/{}?options={}".format(
            picking.id, options
        )
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }
