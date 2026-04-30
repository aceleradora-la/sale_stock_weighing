{
    "name": "Sale Stock Weighing",
    "version": "19.0.3.1.0",
    "category": "Inventory/Sale",
    "summary": "Sell by units, deliver and invoice by weight",
    "description": """
    Allows selling products by unit (e.g. 2 cheese bars) but
    delivering and invoicing by actual weight (kg).

    Features:
    - Configure products as weighed products
    - Set sale UoM (units) and weighing UoM (kg)
    - Weighing assistant for stock operations
    - Invoice by actual delivered weight
    - Weight label printing
    """,
    "author": "Custom",
    "depends": ["sale_stock", "account"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_views.xml",
        "views/sale_order_views.xml",
        "views/stock_picking_type_views.xml",
        "views/stock_picking_views.xml",
        "views/stock_move_views.xml",
        "views/stock_move_line_views.xml",
        "wizards/weighing_wizard_views.xml",
        "report/weighing_label.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sale_stock_weighing/static/src/components/weighing_kanban/**/*",
            "sale_stock_weighing/static/src/components/weighing_record/**/*",
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "auto_install": False,
}
