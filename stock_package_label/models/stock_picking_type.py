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
             "ZPL: para impresoras Zebra (térmica).\n\n"
             "Para configurar la impresora ZPL por defecto:\n"
             "IoT → Dispositivos → [seleccionar impresora Zebra] "
             "→ pestaña 'Informes de la impresora' → agregar la acción "
             "'Etiqueta de Bulto (ZPL)'.",
    )
