from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    remote_measure_device_id = fields.Many2one(
        comodel_name="remote.measure.device",
        string="Default Remote Measure Device",
        help="Default device used by the remote_measure widget for this user.",
    )
