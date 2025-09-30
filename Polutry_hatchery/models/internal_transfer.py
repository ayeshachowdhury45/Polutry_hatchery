from odoo import models, fields, api
from datetime import date

class InternalTransfer(models.Model):
    _name = 'internal.transfer'
    _description = 'Internal Transfer of Chicks'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # -----------------------
    # Main Fields
    # -----------------------
    packaging_id = fields.Many2one(
        'chick.packaging', string="Source Packaging", readonly=True
    )
    source_location = fields.Many2one(
        'stock.location', string="Source Location", required=True, tracking=True
    )
    destination_location = fields.Many2one(
        'stock.location', string="Destination Location", required=True, tracking=True
    )
    chicks_count = fields.Integer(
        string="Chicks Count", required=True, tracking=True
    )
    transfer_date = fields.Date(
        string="Transfer Date", default=lambda self: date.today(), required=True, tracking=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('delivered', 'Delivered'),
    ], default='draft', string="Status", tracking=True)
    picking_id = fields.Many2one(
        'stock.picking', string="Related Picking", readonly=True, copy=False
    )
    note = fields.Text(string="Notes")

    _sql_constraints = [
        ('positive_chicks', 'CHECK(chicks_count > 0)', 'Chicks count must be greater than 0!'),
    ]

    # -----------------------
    # Stage Actions
    # -----------------------
    def action_done(self):
        """Create stock picking and moves, mark transfer as done"""
        Product = self.env['product.product']
        PickingType = self.env['stock.picking.type']

        # Get the Day-Old Chicks product
        product_chicks = Product.search([('name', '=', 'Day-Old Chicks')], limit=1)
        if not product_chicks:
            raise ValueError("Product 'Day-Old Chicks' not found.")

        # Get Internal Picking Type
        picking_type = PickingType.search([('code', '=', 'internal')], limit=1)
        if not picking_type:
            raise ValueError("No Internal Picking Type found in Inventory.")

        for rec in self:
            # Create picking
            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'location_id': rec.source_location.id,
                'location_dest_id': rec.destination_location.id,
                'scheduled_date': rec.transfer_date,
                'origin': rec.note or f'Transfer from Packaging {rec.packaging_id.id}' if rec.packaging_id else 'Chick Internal Transfer',
            })

            # Create stock move
            self.env['stock.move'].create({
                'name': 'Chick Transfer',
                'product_id': product_chicks.id,
                'product_uom_qty': rec.chicks_count,
                'product_uom': product_chicks.uom_id.id,
                'picking_id': picking.id,
                'location_id': rec.source_location.id,
                'location_dest_id': rec.destination_location.id,
            })

            # Update transfer record
            rec.picking_id = picking.id
            rec.state = 'done'
            rec.message_post(body=f"Internal Transfer marked as Done: {rec.chicks_count} chicks.")

    def action_delivered(self):
        """Validate picking to update stock and mark as delivered"""
        for rec in self:
            if not rec.picking_id:
                raise ValueError("No related picking found. Mark as Done first.")

            # Confirm, assign, and validate picking
            rec.picking_id.action_confirm()
            rec.picking_id.action_assign()
            rec.picking_id.button_validate()

            # Update transfer state
            rec.state = 'delivered'
            rec.message_post(body="Chicks successfully delivered and stock updated.")
