import socket

from odoo import _, fields, models


class RemoteMeasureDevice(models.Model):
    _name = "remote.measure.device"
    _description = "Balanza Remota"

    name = fields.Char(string="Name", required=True)
    host = fields.Char(
        string="Host",
        help="Dirección IP o nombre de host del dispositivo.",
    )
    port = fields.Integer(
        string="Puerto",
        default=5000,
        help="Puerto TCP/WebSocket expuesto por el dispositivo.",
    )
    connection_mode = fields.Selection(
        selection=[
            ("websocket", "WebSocket"),
            ("webservice", "Web Service"),
        ],
        string="Modo de Conexión",
        default="websocket",
        required=True,
    )
    protocol = fields.Selection(
        selection=[
            ("f501", "Balanza F501 (lectura continua)"),
        ],
        string="Protocol",
        default="f501",
        required=True,
    )
    uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="UdM del Dispositivo",
        help="Unidad en que el dispositivo reporta los valores (ej: kg). "
        "Odoo convierte automáticamente a la UdM del campo.",
    )
    read_instantly = fields.Boolean(
        string="Leer Inmediatamente",
        default=True,
        help="Acepta la primera lectura estable sin esperar confirmación del usuario.",
    )
    non_stop_read = fields.Boolean(
        string="Lectura Continua",
        help="Sigue leyendo y actualizando el campo hasta que el usuario detenga la sesión.",
    )
    read_interval = fields.Float(
        string="Intervalo de Lectura (s)",
        default=1.0,
        help="Segundos mínimos entre lecturas sucesivas en modo continuo.",
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
                    "title": _("Conexión exitosa"),
                    "message": _("%(name)s (%(host)s:%(port)s) responde correctamente.", name=self.name, host=self.host, port=self.port),
                    "type": "success",
                    "sticky": False,
                },
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Falló la conexión"),
                "message": _("No se pudo conectar a %(host)s:%(port)s. Verificá la IP, el puerto y el firewall.", host=self.host, port=self.port),
                "type": "danger",
                "sticky": False,
            },
        }
