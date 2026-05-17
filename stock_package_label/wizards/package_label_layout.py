import socket

from odoo import api, fields, models
from odoo.exceptions import UserError


class PackageLabelLayout(models.TransientModel):
    """Wizard para configurar e imprimir etiquetas de bultos.

    Permite elegir:
    - Formato: PDF (con grilla de columnas) o ZPL (Zebra)
    - Columnas por fila y filas por página  (solo PDF)
    - Dirección IP:puerto de la impresora Zebra (solo ZPL, envío TCP directo)
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
    # ── Opciones ZPL ────────────────────────────────────────────────
    printer_address = fields.Char(
        string="Impresora Zebra (IP:Puerto)",
        help="Dirección de la impresora en red. Ejemplo: 192.168.1.50:9100\n"
             "Las impresoras Zebra aceptan ZPL crudo por TCP/9100 sin drivers.\n"
             "Si se deja vacío, se descarga el archivo ZPL para imprimir manualmente.",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        picking_id = self.env.context.get("default_picking_id")
        if picking_id:
            picking = self.env["stock.picking"].browse(picking_id)
            ptype = picking.picking_type_id
            res["label_format"] = ptype.package_label_format or "pdf"
            res["printer_address"] = ptype.package_label_printer_address or ""
        return res

    # ── Acción principal ─────────────────────────────────────────────

    def action_print(self):
        """Genera o envía las etiquetas según el formato elegido."""
        self.ensure_one()
        picking = self.picking_id
        if self.label_format == "zpl":
            return self._print_zpl(picking)
        return self._print_pdf(picking)

    # ── PDF con grilla ───────────────────────────────────────────────

    def _print_pdf(self, picking):
        report = self.env.ref(
            "stock_package_label.action_report_package_label_pdf"
        )
        return report.report_action(
            picking,
            data={
                "columns": max(1, self.columns),
                "rows_per_page": max(1, self.rows_per_page),
            },
        )

    # ── ZPL directo o descarga ───────────────────────────────────────

    def _print_zpl(self, picking):
        report = self.env.ref(
            "stock_package_label.action_report_package_label_zpl"
        )
        addr = (self.printer_address or "").strip()
        if addr:
            return self._send_tcp(report, picking, addr)
        # Sin dirección: descarga del .txt ZPL.
        return report.report_action(picking)

    def _send_tcp(self, report, picking, address):
        """Envía el ZPL directamente a la impresora por TCP/IP.

        Las Zebra aceptan ZPL crudo en el puerto 9100 por defecto.
        Formato address: "192.168.1.50" o "192.168.1.50:9100"
        """
        host, _, port_str = address.partition(":")
        try:
            port = int(port_str) if port_str else 9100
        except ValueError:
            raise UserError(
                "El puerto de la impresora no es válido. "
                "Use el formato IP:Puerto, ej: 192.168.1.50:9100"
            )

        zpl_bytes, _ = report._render(report.report_name, picking.ids)

        try:
            with socket.create_connection((host.strip(), port), timeout=8) as sock:
                sock.sendall(zpl_bytes)
        except OSError as e:
            raise UserError(
                "No se pudo conectar a la impresora %s:%s.\n"
                "Verificá que:\n"
                "- La impresora esté encendida y en la red.\n"
                "- La IP y el puerto sean correctos.\n"
                "- El puerto 9100 esté habilitado en la impresora.\n\n"
                "Error técnico: %s" % (host, port, e)
            )

        return {"type": "ir.actions.act_window_close"}
