import socket

from odoo import _, fields, models


class RemoteMeasureDevice(models.Model):
    _name = "remote.measure.device"
    _description = "Remote Measure Device"

    name = fields.Char(string="Name", required=True)
    host = fields.Char(
        string="Host",
        help="IP address or hostname of the remote device.",
    )
    port = fields.Integer(
        string="Port",
        default=5000,
        help="TCP/WebSocket port exposed by the device.",
    )
    connection_mode = fields.Selection(
        selection=[
            ("websocket", "Web Sockets"),
            ("webservice", "Web Services"),
        ],
        string="Connection Mode",
        default="websocket",
        required=True,
    )
    protocol = fields.Selection(
        selection=[
            ("f501", "F501 Scale (continuous stream)"),
        ],
        string="Protocol",
        default="f501",
        required=True,
    )
    uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Device Unit of Measure",
        help="Unit in which the device reports values (e.g. kg). "
        "Odoo will convert to the field's UoM automatically.",
    )
    read_instantly = fields.Boolean(
        string="Read Instantly",
        default=True,
        help="Accept the first stable reading without waiting for user confirmation.",
    )
    non_stop_read = fields.Boolean(
        string="Non-stop Read",
        help="Keep reading and updating the field until the user stops the session.",
    )
    read_interval = fields.Float(
        string="Read Interval (s)",
        default=1.0,
        help="Minimum seconds between successive readings in non-stop mode.",
    )

    def test_tcp_connection(self):
        """Try a raw TCP connection to verify device reachability (2 s timeout)."""
        self.ensure_one()
        if not self.host or not self.port:
            return False
        try:
            conn = socket.create_connection((self.host, self.port), timeout=2)
            conn.close()
            return True
        except OSError:
            return False

    def action_test_connection(self):
        self.ensure_one()
        if self.test_tcp_connection():
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection successful"),
                    "message": _("%(name)s (%(host)s:%(port)s) is reachable.", name=self.name, host=self.host, port=self.port),
                    "type": "success",
                    "sticky": False,
                },
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Connection failed"),
                "message": _("Could not reach %(host)s:%(port)s. Check the IP, port, and firewall rules.", host=self.host, port=self.port),
                "type": "danger",
                "sticky": False,
            },
        }
