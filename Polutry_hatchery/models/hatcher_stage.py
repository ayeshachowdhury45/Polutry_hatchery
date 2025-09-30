from odoo import models, fields, api

# -----------------------
# Hatcher Machine
# -----------------------
class HatcherMachine(models.Model):
    _name = 'hatchery.hatcher.machine'
    _description = 'Hatcher Machine'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True)
    capacity = fields.Integer(default=50000)
    hatcher_stage_ids = fields.One2many(
        'hatchery.hatcher.stage', 'machine_id', string="Hatcher Stages"
    )


# -----------------------
# Hatcher Stage
# -----------------------
class HatcherStage(models.Model):
    _name = 'hatchery.hatcher.stage'
    _description = 'Hatcher Stage'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    setter_stage_id = fields.Many2one(
        'hatchery.setter.stage', string='Setter Stage', required=True, tracking=True)
    machine_id = fields.Many2one(
        'hatchery.hatcher.machine', string='Hatcher Machine', required=True)
    quantity_loaded = fields.Integer(string='Quantity Loaded', required=True)
    mortality = fields.Integer(string='Mortality', default=0)
    success_rate = fields.Float(
        string='Success Rate (%)', compute='_compute_success_rate', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_hatcher', 'In Hatcher'),
        ('ready_for_packaging', 'Ready for Packaging'),
        ('done', 'Done')
    ], string='Status', default='in_hatcher', tracking=True)

    show_move_to_packaging = fields.Boolean(
        string="Show Move to Packaging Button",
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
        'hatchery.hatcher.stage.equipment', 'hatcher_stage_id', string="Equipments")
    material_ids = fields.One2many(
        'hatchery.hatcher.stage.material', 'hatcher_stage_id', string="Materials")
    temperature_ids = fields.One2many(
        'hatchery.hatcher.stage.temperature', 'hatcher_stage_id', string="Temperature")
    sanitizer_ids = fields.One2many(
        'hatchery.hatcher.stage.sanitizer', 'hatcher_stage_id', string="Sanitizer Cleaning")

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

    @api.depends('state')
    def _compute_button_visibility(self):
        for record in self:
            record.show_move_to_packaging = record.state == 'in_hatcher'
            record.show_done = record.state == 'ready_for_packaging'

    def action_move_to_packaging(self):
        """Move batch from Hatcher to Packaging (Boxing Chicks)"""
        ChickPackaging = self.env['chick.packaging']

        for rec in self:
            rec.state = 'ready_for_packaging'
            rec.message_post(
                body=f"Hatcher Stage ready for packaging. Mortality: {rec.mortality}, "
                     f"Success Rate: {rec.success_rate:.1f}%"
            )

            # Compute chicks surviving Hatcher
            chicks_after_hatcher = rec.quantity_loaded - rec.mortality

            # Create Chick Packaging record
            ChickPackaging.create({
                'hatcher_stage_id': rec.id,
                'chicks_count': chicks_after_hatcher,
                # boxes_count will be computed automatically
            })

    def action_done(self):
        for rec in self:
            rec.state = 'done'
            rec.message_post(body="Hatcher Stage marked as Done")

    # -----------------------
    # Override create to copy related records from Setter Stage
    # -----------------------
    @api.model
    def create(self, vals):
        stage = super(HatcherStage, self).create(vals)
        setter_stage = stage.setter_stage_id

        if setter_stage:
            # Copy Equipments
            for eq in setter_stage.equipment_ids:
                self.env['hatchery.hatcher.stage.equipment'].create({
                    'hatcher_stage_id': stage.id,
                    'equipment_id': eq.equipment_id.id if eq.equipment_id else False,
                    'lot': eq.lot or '',
                    'qty': eq.qty or 0,
                    'date': eq.date,
                    'production_summary': eq.production_summary or '',
                })
            # Copy Materials
            for mat in setter_stage.material_ids:
                self.env['hatchery.hatcher.stage.material'].create({
                    'hatcher_stage_id': stage.id,
                    'product_id': mat.product_id.id if mat.product_id else False,
                    'description': mat.description,
                    'lot': mat.lot,
                    'qty': mat.qty,
                    'uom_id': mat.uom_id.id if mat.uom_id else False,
                    'unit_price': mat.unit_price,
                    'subtotal': mat.subtotal,
                })
            # Copy Temperature
            for temp in setter_stage.temperature_ids:
                self.env['hatchery.hatcher.stage.temperature'].create({
                    'hatcher_stage_id': stage.id,
                    'date': temp.date,
                    'min_temp': temp.min_temp,
                    'max_temp': temp.max_temp,
                    'avg_temp': temp.avg_temp,
                    'humidity': temp.humidity,
                    'user_id': temp.user_id.id if temp.user_id else False,
                })
            # Copy Sanitizer
            for san in setter_stage.sanitizer_ids:
                self.env['hatchery.hatcher.stage.sanitizer'].create({
                    'hatcher_stage_id': stage.id,
                    'checklist': san.checklist,
                    'date': san.date,
                    'user_id': san.user_id.id if san.user_id else False,
                })
        return stage


# -----------------------
# Related Models: Equipment, Material, Temperature, Sanitizer
# -----------------------
class HatcherStageEquipment(models.Model):
    _name = 'hatchery.hatcher.stage.equipment'
    _description = 'Hatcher Stage Equipment'

    hatcher_stage_id = fields.Many2one('hatchery.hatcher.stage', string="Hatcher Stage", ondelete='cascade')
    equipment_id = fields.Many2one('stock.location', string="Equipment / Rack", ondelete='set null')
    lot = fields.Char(string="Lot")
    qty = fields.Integer(string="Quantity")
    date = fields.Date(string="Date")
    production_summary = fields.Text(string="Production Summary")


class HatcherStageMaterial(models.Model):
    _name = 'hatchery.hatcher.stage.material'
    _description = 'Hatcher Stage Material'

    hatcher_stage_id = fields.Many2one('hatchery.hatcher.stage', string="Hatcher Stage", ondelete='cascade')
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


class HatcherStageTemperature(models.Model):
    _name = 'hatchery.hatcher.stage.temperature'
    _description = 'Hatcher Stage Temperature'

    hatcher_stage_id = fields.Many2one('hatchery.hatcher.stage', string="Hatcher Stage", ondelete='cascade')
    date = fields.Datetime(string="Date")
    min_temp = fields.Float(string="Min Temperature")
    max_temp = fields.Float(string="Max Temperature")
    avg_temp = fields.Float(string="Average Temperature")
    humidity = fields.Float(string="Humidity (%)")
    user_id = fields.Many2one('res.users', string="Recorded By", ondelete='set null')


class HatcherStageSanitizer(models.Model):
    _name = 'hatchery.hatcher.stage.sanitizer'
    _description = 'Hatcher Stage Sanitizer'

    hatcher_stage_id = fields.Many2one('hatchery.hatcher.stage', string="Hatcher Stage", ondelete='cascade')
    checklist = fields.Text(string="Checklist")
    date = fields.Datetime(string="Date")
    user_id = fields.Many2one('res.users', string="Checked By", ondelete='set null')
