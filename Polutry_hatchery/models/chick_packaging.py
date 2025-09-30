from odoo import models, fields, api

class ChickPackaging(models.Model):
    _name = 'chick.packaging'
    _description = 'Chick Packaging'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # enables chatter

    # -----------------------
    # Main Fields
    # -----------------------
    hatcher_stage_id = fields.Many2one(
        'hatchery.hatcher.stage', string="Hatcher Stage", required=True, tracking=True
    )
    chicks_count = fields.Integer(
        string="Chicks Count", required=True, tracking=True
    )
    boxes_count = fields.Integer(
        string="Boxes Count", compute='_compute_boxes_count', store=True
    )
    packaging_mortality = fields.Integer(
        string="Packaging Mortality", default=0, tracking=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('ready_for_transfer', 'Ready for Transfer'),
        ('done', 'Done')
    ], default='draft', string="Status", tracking=True)
    note = fields.Text(string="Notes")  # Optional notebook for additional info

    # -----------------------
    # Computed Fields
    # -----------------------
    @api.depends('chicks_count')
    def _compute_boxes_count(self):
        for rec in self:
            rec.boxes_count = rec.chicks_count // 40  # 40 chicks per box

    # -----------------------
    # Stage Actions
    # -----------------------
    def action_ready_for_transfer(self):
        """Mark packaging ready and create draft internal transfer"""
        InternalTransfer = self.env['internal.transfer']

        for rec in self:
            # Mark packaging ready
            rec.state = 'ready_for_transfer'
            rec.message_post(
                body=f"{rec.chicks_count} chicks packaged in {rec.boxes_count} boxes. "
                     f"Mortality: {rec.packaging_mortality}"
            )

            # Calculate transferable quantity
            transfer_qty = rec.chicks_count - rec.packaging_mortality
            if transfer_qty <= 0:
                rec.message_post(body="No chicks available to transfer after mortality.")
                continue

            # Create a draft internal transfer linked to this packaging
            transfer = InternalTransfer.create({
                'chicks_count': transfer_qty,
                'transfer_date': fields.Date.today(),
                'note': f"From Packaging ID: {rec.id}",
                'packaging_id': rec.id,  # link to packaging
            })

            rec.message_post(body=f"Draft Internal Transfer created: {transfer.id}")

    def action_done(self):
        for rec in self:
            rec.state = 'done'
            rec.message_post(body="Chick Packaging marked as Done")
