{
    "name": "Stock Package Label",
    "version": "19.0.1.0.0",
    "category": "Inventory",
    "summary": "Imprime etiquetas de bultos (PDF o ZPL) desde órdenes de entrega",
    "description": """
Stock Package Label
===================

Permite imprimir etiquetas de bultos para órdenes de entrega cuando se indica
la cantidad de bultos a despachar.

Características
---------------
- Campo "Número de Bultos" en la orden de entrega (editable o calculado desde
  los paquetes de Odoo).
- Botón de impresión visible cuando hay al menos un bulto definido.
- Etiqueta PDF: una página por bulto, con diseño tipo etiqueta de envío.
- Etiqueta ZPL: formato para impresoras Zebra, una etiqueta por bulto.
- Formato configurable por tipo de operación (PDF o ZPL).

Datos en la etiqueta
--------------------
- Número de bulto (X / N)
- Nombre y dirección del cliente
- Número de orden de venta
- Número de remito / picking
- Fecha de entrega
- Peso de envío
- Nombre de la empresa
""",
    "author": "Aceleradora LA",
    "website": "https://github.com/aceleradora-la/sale_stock_weighing",
    "license": "LGPL-3",
    "depends": [
        "stock",
        "sale_stock",
    ],
    "data": [
        "views/stock_picking_type_views.xml",
        "views/stock_picking_views.xml",
        "report/package_label.xml",
    ],
    "installable": True,
    "auto_install": False,
}
