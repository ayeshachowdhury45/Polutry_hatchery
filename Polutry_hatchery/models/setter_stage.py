from odoo import models, fields, api

# -----------------------
# Setter Machine
# -----------------------
class SetterMachine(models.Model):
    _name = 'hatchery.setter.machine'
    _description = 'Setter Machine'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True)
    capacity = fields.Integer(default=100000)
    setter_stage_ids = fields.One2many(
        'hatchery.setter.stage', 'machine_id', string="Setter Stages"
    )


# -----------------------
# Setter Stage
# -----------------------
class SetterStage(models.Model):
    _name = 'hatchery.setter.stage'
    _description = 'Setter Stage'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # -----------------------
    # Main fields
    # -----------------------
    egg_batch_id = fields.Many2one(
        'hatchery.egg.batch', string='Egg Batch', required=True, tracking=True)
    machine_id = fields.Many2one(
        'hatchery.setter.machine', string='Setter Machine', required=True)
    quantity_loaded = fields.Integer(string='Quantity Loaded', required=True)
    mortality = fields.Integer(string='Mortality', default=0)
    start_date = fields.Datetime(string='Start Date', default=fields.Datetime.now)
    end_date = fields.Datetime(string='End Date')  # Added to fix AttributeError
    success_rate = fields.Float(
        string='Success Rate (%)', compute='_compute_success_rate', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_setter', 'In Setter'),
        ('ready_for_hatcher', 'Ready for Hatcher'),
        ('done', 'Done')
    ], string='Status', default='in_setter', tracking=True)

    show_move_to_hatcher = fields.Boolean(
        string="Show Move to Hatcher Button",
        compute='_compute_button_visibility'
    )
    show_done = fields.Boolean(
        string="Show Done Button",
        compute='_compute_button_visibility'
    )

    # -----------------------
    # One2many relationships
    # -----------------------
    equipment_ids = fields.One2many(
        'hatchery.setter.stage.equipment', 'setter_stage_id', string="Equipments")
    material_ids = fields.One2many(
        'hatchery.setter.stage.material', 'setter_stage_id', string="Materials")
    temperature_ids = fields.One2many(
        'hatchery.setter.stage.temperature', 'setter_stage_id', string="Temperature")
    sanitizer_ids = fields.One2many(
        'hatchery.setter.stage.sanitizer', 'setter_stage_id', string="Sanitizer Cleaning")

    # -----------------------
    # Compute success rate
    # -----------------------
    @api.depends('quantity_loaded', 'mortality')
    def _compute_success_rate(self):
        for record in self:
            if record.quantity_loaded:
                record.success_rate = ((record.quantity_loaded - (record.mortality or 0)) / record.quantity_loaded) * 100
            else:
                record.success_rate = 0

    # -----------------------
    # Compute button visibility
    # -----------------------
    @api.depends('state')
    def _compute_button_visibility(self):
        for record in self:
            record.show_move_to_hatcher = record.state == 'in_setter'
            record.show_done = record.state == 'ready_for_hatcher'

    # -----------------------
    # Override create to copy related records
    # -----------------------
    @api.model
    def create(self, vals):
        stage = super(SetterStage, self).create(vals)
        egg = stage.egg_batch_id

        if egg:
            # Copy Equipments
            for eq in egg.equipment_ids:
                self.env['hatchery.setter.stage.equipment'].create({
                    'setter_stage_id': stage.id,
                    'equipment_id': eq.equipment_id.id if eq.equipment_id else False,
                    'lot': eq.lot or '',
                    'qty': eq.qty or 0,
                    'date': eq.date,
                    'production_summary': eq.production_summary or '',
                })

            # Copy Materials
            for mat in egg.material_ids:
                self.env['hatchery.setter.stage.material'].create({
                    'setter_stage_id': stage.id,
                    'product_id': mat.product_id.id if mat.product_id else False,
                    'description': mat.description,
                    'lot': mat.lot,
                    'qty': mat.qty,
                    'uom_id': mat.uom_id.id if mat.uom_id else False,
                    'unit_price': mat.unit_price,
                    'subtotal': mat.subtotal,
                })

            # Copy Temperature
            for temp in egg.temperature_ids:
                self.env['hatchery.setter.stage.temperature'].create({
                    'setter_stage_id': stage.id,
                    'date': temp.date,
                    'min_temp': temp.min_temp,
                    'max_temp': temp.max_temp,
                    'avg_temp': temp.avg_temp,
                    'humidity': temp.humidity,
                    'user_id': temp.user_id.id if temp.user_id else False,
                })

            # Copy Sanitizer
            for san in egg.sanitizer_ids:
                self.env['hatchery.setter.stage.sanitizer'].create({
                    'setter_stage_id': stage.id,
                    'checklist': san.checklist,
                    'date': san.date,
                    'user_id': san.user_id.id if san.user_id else False,
                })

        return stage

    # -----------------------
    # Stage actions
    # -----------------------
    def action_move_to_hatcher(self):
        """Move batch to Hatcher stage (3-day incubation)"""
        HatcherStage = self.env['hatchery.hatcher.stage']
        HatcherMachine = self.env['hatchery.hatcher.machine']

        for rec in self:
            rec.state = 'ready_for_hatcher'
            rec.end_date = fields.Datetime.now()

            eggs_after_setter = rec.quantity_loaded - rec.mortality
            eggs_to_hatcher = max(eggs_after_setter, 0)

            success_rate = 0
            if eggs_after_setter > 0:
                success_rate = (eggs_to_hatcher / eggs_after_setter) * 100

            machine = HatcherMachine.search([], limit=1)
            if not machine:
                machine = HatcherMachine.create({'name': 'Default Hatcher Machine', 'capacity': 50000})

            HatcherStage.create({
                'setter_stage_id': rec.id,
                'machine_id': machine.id,
                'quantity_loaded': eggs_after_setter,
                'mortality': rec.mortality,
                'success_rate': success_rate,
                'state': 'in_hatcher',
            })

            rec.message_post(body=f"Moved {eggs_after_setter} eggs to Hatcher Stage. "
                                  f"Mortality: {rec.mortality}, Success Rate: {success_rate:.1f}%")

    def action_done(self):
        for rec in self:
            rec.state = 'done'


# -----------------------
# Related Models
# -----------------------
class SetterStageEquipment(models.Model):
    _name = 'hatchery.setter.stage.equipment'
    _description = 'Setter Stage Equipment'

    setter_stage_id = fields.Many2one('hatchery.setter.stage', string="Setter Stage", ondelete='cascade')
    equipment_id = fields.Many2one('stock.location', string="Equipment / Rack", ondelete='set null')
    lot = fields.Char(string="Lot")
    qty = fields.Integer(string="Quantity")
    date = fields.Date(string="Date")
    production_summary = fields.Text(string="Production Summary")


class SetterStageMaterial(models.Model):
    _name = 'hatchery.setter.stage.material'
    _description = 'Setter Stage Material'

    setter_stage_id = fields.Many2one('hatchery.setter.stage', string="Setter Stage", ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Product", ondelete='set null')
    description = fields.Text(string="Description")
    lot = fields.Char(string="Lot")
    qty = fields.Float(string="Quantity")
    uom_id = fields.Many2one('uom.uom', string="Unit of Measure", ondelete='set null')
    unit_price = fields.Float(string="Unit Price")
    subtotal = fields.Float(string="Subtotal", compute="_compute_subtotal", store=True)

    @api.depends('qty', 'unit_price')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.qty * rec.unit_price if rec.qty and rec.unit_price else 0.0


class SetterStageTemperature(models.Model):
    _name = 'hatchery.setter.stage.temperature'
    _description = 'Setter Stage Temperature'

    setter_stage_id = fields.Many2one('hatchery.setter.stage', string="Setter Stage", ondelete='cascade')
    date = fields.Datetime(string="Date")
    min_temp = fields.Float(string="Min Temperature")
    max_temp = fields.Float(string="Max Temperature")
    avg_temp = fields.Float(string="Average Temperature")
    humidity = fields.Float(string="Humidity (%)")
    user_id = fields.Many2one('res.users', string="Recorded By", ondelete='set null')


class SetterStageSanitizer(models.Model):
    _name = 'hatchery.setter.stage.sanitizer'
    _description = 'Setter Stage Sanitizer'

    setter_stage_id = fields.Many2one('hatchery.setter.stage', string="Setter Stage", ondelete='cascade')
    checklist = fields.Text(string="Checklist")
    date = fields.Datetime(string="Date")
    user_id = fields.Many2one('res.users', string="Checked By", ondelete='set null')
