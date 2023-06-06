# -*- coding: utf-8 -*-
##############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#    Copyright (C) 2022-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: ASWATHI C (<https://www.cybrosys.com>)
#    you can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    GENERAL PUBLIC LICENSE (LGPL v3) along with this program.
#    If not, see <https://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import fields, models, api


class PlannedWork(models.Model):
    _name = 'workshop.planned.work'

    planned_work = fields.Many2one('product.product', string='Planned work', domain=[('type', '=', 'service')])
    time_spent = fields.Float(string='Estimated Time')
    work_date = fields.Datetime(string='Date')  # Date of work planned:planned date
    responsible = fields.Many2one('res.users', string='Responsible')
    work_id = fields.Many2one('car.workshop', string="Work id")
    work_cost = fields.Float(string="Service Cost",digits='Product Price')
    completed = fields.Boolean(string="Completed")
    duration = fields.Float(string='Duration')
    work_date2 = fields.Datetime(string='Date')  # Date of work completed/done:completed date

    @api.onchange('planned_work')
    def get_price(self):
        self.work_cost = self.planned_work and self.planned_work.lst_price or 0.0


class MaterialUsed(models.Model):
    _name = 'workshop.material.used'

    material = fields.Many2one('product.product', string='Products')
    amount = fields.Integer(string='Quantity',default=1)
    price = fields.Float(string='Unit Price',digits='Product Price')
    material_id = fields.Many2one('car.workshop')

    @api.onchange('material')
    def get_price(self):
        self.price = self.material and self.material.lst_price or 0.0
