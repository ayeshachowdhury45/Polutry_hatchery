import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_egg_product = fields.Boolean(string="Is Egg Product?")


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_egg_batch = fields.Boolean(string="Is Egg Batch?", default=False)
    egg_batch_id = fields.Many2one('hatchery.egg.batch', string="Egg Batch")

    def button_validate(self):
        _logger.info("Button Validate called for Picking(s): %s", self.mapped('name'))
        res = super(StockPicking, self).button_validate()

        for picking in self:
            _logger.info("Checking all moves for egg products in Picking: %s", picking.name)

            # Use all moves, including packaged ones
            egg_moves = picking.move_ids.filtered(
                lambda m: m.product_id.product_tmpl_id.is_egg_product
            )

            if egg_moves:
                _logger.info("Found %d egg move lines in Picking: %s", len(egg_moves), picking.name)

                if not picking.egg_batch_id:
                    total_qty = sum(egg_moves.mapped('product_uom_qty'))
                    _logger.info("Creating Egg Batch with total qty: %s for Picking: %s", total_qty, picking.name)

                    batch = self.env['hatchery.egg.batch'].create({
                        'batch_no': 'New',
                        'date_received': picking.scheduled_date or fields.Date.today(),
                        'qty_received': total_qty,
                        'company_id': picking.company_id.id,
                        'notes': f"Auto-created from Stock Picking {picking.name}",
                    })

                    picking.egg_batch_id = batch.id
                    _logger.info("Egg Batch %s created and linked to Picking %s", batch.batch_no, picking.name)
                else:
                    _logger.info("Picking %s already has an Egg Batch linked: %s", picking.name, picking.egg_batch_id.batch_no)
            else:
                _logger.info("No egg products found in Picking: %s", picking.name)

        return res
