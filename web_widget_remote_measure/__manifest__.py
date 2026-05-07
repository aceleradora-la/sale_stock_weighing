{
    "name": "Remote Measure Devices Input",
    "version": "19.0.1.0.0",
    "category": "Stock",
    "summary": "Connect to remote weighing devices (F501/WebSocket) to record measures",
    "description": """
Remote Measure Devices Input
=============================

Allows connecting to remote measurement devices (e.g. weight scales) over
the local network and recording their readings directly into Odoo fields.

Supported connections
---------------------
- WebSocket (default)

Supported protocols
-------------------
- F501 (continuous weight scale stream)

Configuration
-------------
1. Go to *Inventory > Configuration > Devices > Remote Devices* and add
   the IP/port of your scale.
2. In *Preferences* (top-right user menu), set your default device.
3. On any field that uses the ``remote_measure`` widget, a balance icon
   will appear. Click it to start reading from the scale; click the
   blinking icon to accept the reading.
""",
    "author": "Aceleradora LA",
    "website": "https://github.com/aceleradora-la/sale_stock_weighing",
    "license": "LGPL-3",
    "depends": ["web", "uom"],
    "data": [
        "security/ir.model.access.csv",
        "views/remote_measure_device_views.xml",
        "views/res_users_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "web_widget_remote_measure/static/src/remote_measure_field/remote_measure_field.esm.js",
            "web_widget_remote_measure/static/src/remote_measure_field/remote_measure_field.xml",
            "web_widget_remote_measure/static/src/systray/systray_device_selector.esm.js",
            "web_widget_remote_measure/static/src/systray/systray_device_selector.xml",
        ],
    },
    "installable": True,
    "auto_install": False,
}
