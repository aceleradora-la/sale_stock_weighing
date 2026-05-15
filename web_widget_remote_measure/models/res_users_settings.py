from odoo import fields, models


class ResUsersSettings(models.Model):
    _inherit = "res.users.settings"

    remote_measure_device_id = fields.Many2one(
        comodel_name="remote.measure.device",
        string="Balanza por Defecto",
        help="Balanza por defecto usada por el asistente de pesaje para este usuario.",
    )
