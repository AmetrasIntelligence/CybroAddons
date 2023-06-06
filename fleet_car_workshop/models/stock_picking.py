from odoo import fields, models

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    car_workshop_id = fields.Many2one('car.workshop',string="Car Workshop")