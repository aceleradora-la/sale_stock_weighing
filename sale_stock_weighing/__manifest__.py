{
    "name": "Sale Stock Weighing",
    "version": "19.0.9.1.0",
    "category": "Inventory/Sale",
    "summary": "Sell by units, deliver and invoice by weight",
    "description": """
Sale Stock Weighing
===================

Allows selling products by unit (e.g. 5 ham pieces) but delivering and
invoicing by actual weight (kg).

Features
--------
- Configure products as weighed products with a separate weighing UoM.
- Sales order line tracks piece count (x_piece_count) and estimated weight.
- Weighing assistant for stock operations (kanban + wizard).
- Operation lock to avoid concurrent weighing.
- Remote scale support via WebSocket/F501 (requires web_widget_remote_measure).
- Pricelist with three pricing modes for $/weight: fixed, discount, formula.
- Invoice generated using the actual delivered weight × price/kg.
- Weight label printing in PDF or ZPL format, including piece price.
- Cotización and factura reports show pieces + weight + price/kg columns.
- Lot tracking: each lot = one physical piece; piece count derived automatically.
""",
    "author": "Aceleradora LA",
    "website": "https://github.com/aceleradora-la/sale_stock_weighing",
    "license": "LGPL-3",
    "depends": [
        "sale_stock",
        "purchase_stock",
        "account",
        "base_setup",
        "web_widget_remote_measure",
        "l10n_ar_stock_ux",
        # El peso del encabezado del remito lo agrega l10n_ar_stock_delivery:
        # se depende de él para que el xpath que lo corrige tenga su anclaje.
        "l10n_ar_stock_delivery",
        "stock_picking_batch",
    ],
    "post_init_hook": "post_init_hook",
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/res_company_views.xml",
        "views/product_views.xml",
        "views/sale_order_views.xml",
        "views/purchase_order_views.xml",
        "views/stock_picking_type_views.xml",
        "views/stock_picking_views.xml",
        "views/stock_move_views.xml",
        "views/stock_move_line_views.xml",
        "views/account_move_line_views.xml",
        "views/product_pricelist_views.xml",
        "views/stock_picking_batch_views.xml",
        "wizards/weighing_wizard_views.xml",
        "report/weighing_label.xml",
        "report/sale_order_weighing.xml",
        "report/account_invoice_weighing.xml",
        "report/stock_picking_weighing.xml",
        "report/weighing_picking_block.xml",
        "report/batch_picking_weighing.xml",
        "report/picking_weighing_sheet.xml",
    ],
    "installable": True,
    "auto_install": False,
}
