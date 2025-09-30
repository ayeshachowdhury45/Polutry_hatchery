from odoo import models, fields, api
from odoo.exceptions import UserError

class EggBatch(models.Model):
    _name = 'hatchery.egg.batch'
    _description = 'Egg Batch'
    _rec_name = 'batch_no'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user)
    batch_no = fields.Char(string='Batch / Lot Number', required=True, tracking=True, default=lambda self: 'New')
    date_received = fields.Date(string='Date Received')
    qty_received = fields.Integer(string='Quantity Received')
    broken_qty = fields.Integer(string="Broken Quantity", default=0)
    delivered_qty = fields.Integer(string="Delivered Quantity", default=0)
    
    qty_available = fields.Integer(
        string="Available Quantity",
        compute="_compute_qty_available",
        store=True
    )
    
    break_line_ids = fields.One2many(
        'hatchery.egg.break.history',
        'batch_id',
        string='Break Lines'
    )

    @api.depends('qty_received', 'broken_qty', 'delivered_qty')
    def _compute_qty_available(self):
        for rec in self:
            rec.qty_available = (rec.qty_received or 0) - (rec.broken_qty or 0) - (rec.delivered_qty or 0)

    pre_storage_waste = fields.Integer(string='Pre-storage Waste')
    notes = fields.Text(string='Notes')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_setter', 'In Setter'),
        ('in_hatcher', 'In Hatcher'),
        ('done', 'Done')
    ], string='Status', default='draft', tracking=True)

    # Button visibility
    show_send_to_setter = fields.Boolean(compute='_compute_button_visibility', string="Show Send to Setter Button")
    show_move_to_hatcher = fields.Boolean(compute='_compute_button_visibility', string="Show Move to Hatcher Button")
    show_done = fields.Boolean(compute='_compute_button_visibility', string="Show Done Button")

    @api.depends('state')
    def _compute_button_visibility(self):
        for rec in self:
            rec.show_send_to_setter = rec.state == 'draft'
            rec.show_move_to_hatcher = rec.state == 'in_setter'
            rec.show_done = rec.state == 'in_hatcher'

    # One2many relationships
    egg_selection_ids = fields.One2many('hatchery.egg.selection', 'egg_batch_id', string='Selection of Eggs')
    equipment_ids = fields.One2many('hatchery.egg.equipment', 'egg_batch_id', string='Equipments')
    material_ids = fields.One2many('hatchery.egg.material', 'egg_batch_id', string='Materials')
    temperature_ids = fields.One2many('hatchery.egg.temperature', 'egg_batch_id', string='Temperature')
    sanitizer_ids = fields.One2many('hatchery.egg.sanitizer', 'egg_batch_id', string='Sanitizer Cleaning')

    @api.model
    def create(self, vals):
        if not vals.get('batch_no') or vals['batch_no'] == 'New':
            vals['batch_no'] = self.env['ir.sequence'].next_by_code('hatchery.egg.batch') or 'BATCH-001'
        return super().create(vals)

    # -----------------------
    # Actions
    # -----------------------
    def action_send_to_setter(self):
        SetterStage = self.env['hatchery.setter.stage']
        setter_machines = self.env['hatchery.setter.machine'].search([], order='id asc')
        if not setter_machines:
            setter_machines = self.env['hatchery.setter.machine'].create([
                {'name': f'Default Setter Machine {i+1}', 'capacity': 100000} for i in range(7)
            ])
        for rec in self:
            qty_remaining = rec.qty_received
            for machine in setter_machines:
                if qty_remaining <= 0:
                    break
                qty_for_machine = min(qty_remaining, machine.capacity)
                SetterStage.create({
                    'egg_batch_id': rec.id,
                    'machine_id': machine.id,
                    'quantity_loaded': qty_for_machine,
                    'mortality': 0,
                    'state': 'in_setter',
                })
                qty_remaining -= qty_for_machine
            rec.state = 'in_setter'

    def action_move_to_hatcher(self, mortality=0):
        HatcherStage = self.env['hatchery.hatcher.stage']
        SetterStage = self.env['hatchery.setter.stage']
        for rec in self:
            setter_stages = SetterStage.search([('egg_batch_id', '=', rec.id)])
            total_qty = sum(s.quantity_loaded for s in setter_stages)
            final_qty = total_qty - mortality
            if final_qty < 0:
                raise UserError("Mortality cannot exceed total quantity in Setter Stage.")
            HatcherStage.create({
                'egg_batch_id': rec.id,
                'machine_id': False,
                'quantity_loaded': final_qty,
                'mortality': mortality,
                'state': 'in_hatcher',
            })
            rec.state = 'in_hatcher'

    def action_done(self):
        self.state = 'done'

    def action_break_eggs(self):
        """Process all break lines in notebook"""
        product = self.env['product.product'].search([('name', '=', 'Eggs')], limit=1)
        if not product:
            raise UserError("Product 'Eggs' not found in inventory.")
        for batch in self:
            if not batch.break_line_ids:
                raise UserError("No break lines to process!")
            total_qty_to_scrap = sum(l.break_qty for l in batch.break_line_ids if not l.processed)
            if total_qty_to_scrap > batch.qty_available:
                raise UserError(f"Cannot break more than available {batch.qty_available} eggs.")

            quants = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id.usage', '=', 'internal'),
                ('quantity', '>', 0)
            ], order='quantity desc')
            qty_to_scrap = total_qty_to_scrap
            for quant in quants:
                if qty_to_scrap <= 0:
                    break
                deduct_qty = min(quant.quantity, qty_to_scrap)
                scrap = self.env['stock.scrap'].create({
                    'product_id': product.id,
                    'scrap_qty': deduct_qty,
                    'location_id': quant.location_id.id,
                    'company_id': batch.company_id.id or self.env.company.id,
                })
                scrap.action_validate()
                qty_to_scrap -= deduct_qty
            if qty_to_scrap > 0:
                raise UserError("Not enough eggs in stock to scrap requested quantity.")
            batch.broken_qty += total_qty_to_scrap
            for line in batch.break_line_ids.filtered(lambda l: not l.processed):
                line.processed = True
            batch.message_post(body=f"{total_qty_to_scrap} eggs broken and removed from inventory.")

# -----------------------------
# Egg Break History Model
# -----------------------------
class EggBreakHistory(models.Model):
    _name = 'hatchery.egg.break.history'
    _description = 'Egg Break History'

    batch_id = fields.Many2one('hatchery.egg.batch', string="Egg Batch")
    date = fields.Datetime(string="Date", default=fields.Datetime.now)
    break_qty = fields.Float(string="Broken Quantity", required=True)
    note = fields.Text(string="Note")
    user_id = fields.Many2one('res.users', string="User", default=lambda self: self.env.user)
    processed = fields.Boolean(string="Processed", default=False)

