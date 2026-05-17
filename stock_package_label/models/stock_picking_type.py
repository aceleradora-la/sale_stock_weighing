from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    package_label_format = fields.Selection(
        selection=[
            ("pdf", "PDF"),
            ("zpl", "ZPL (Zebra)"),
        ],
        string="Formato de Etiqueta de Bulto",
        default="pdf",
        help="Formato en que se imprimirán las etiquetas de bultos.\n"
             "PDF: etiqueta en papel, con selector de columnas.\n"
             "ZPL: para impresoras Zebra (térmica).",
    )
    package_label_printer_address = fields.Char(
        string="Impresora ZPL (IP:Puerto)",
        help="Dirección IP y puerto de la impresora Zebra en red.\n"
             "Formato: 192.168.1.100:9100 (el puerto por defecto es 9100).\n"
             "Las impresoras Zebra aceptan ZPL crudo por TCP sin drivers adicionales.\n"
             "Si se configura, el wizard envía la etiqueta directamente sin descarga.",
    )
