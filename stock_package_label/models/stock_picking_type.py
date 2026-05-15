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
             "PDF: etiqueta en papel, una página por bulto.\n"
             "ZPL: para impresoras Zebra (térmica).",
    )
