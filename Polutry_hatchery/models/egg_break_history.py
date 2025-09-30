from odoo import models, fields

class EggBreakHistory(models.Model):
    _name = 'hatchery.egg.break.history'
    _description = 'Egg Break History'

    batch_id = fields.Many2one('hatchery.egg.batch', string="Egg Batch")
    date = fields.Datetime(string="Date", default=fields.Datetime.now)
    break_qty = fields.Float(string="Broken Quantity", required=True)
    note = fields.Text(string="Note")
    user_id = fields.Many2one('res.users', string="User", default=lambda self: self.env.user)
    processed = fields.Boolean(string="Processed", default=False)