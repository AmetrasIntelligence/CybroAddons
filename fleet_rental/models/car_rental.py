# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2019-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Cybrosys Technogies @cybrosys(odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################

from datetime import datetime, date, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, Warning


class CarRentalContract(models.Model):
    _name = 'car.rental.contract'
    _description = 'Fleet Rental Management'
    _inherit = 'mail.thread'

    @api.onchange('rent_start_date', 'rent_end_date')
    def check_availability(self):
        self.vehicle_id = False
        for fleet in self.env['fleet.vehicle'].search([('rental_fleet_reserved_ids', '!=', False)]):
            for fleet_reserve in fleet.rental_fleet_reserved_ids:
                if str(fleet_reserve.date_from) <= str(self.rent_start_date) <= str(fleet_reserve.date_to):
                    fleet.write({'rental_check_availability': False})
                elif str(self.rent_start_date) < str(fleet_reserve.date_from):
                    if str(fleet_reserve.date_from) <= str(self.rent_end_date) <= str(fleet_reserve.date_to):
                        fleet.write({'rental_check_availability': False})
                    elif str(self.rent_end_date) > str(fleet_reserve.date_to):
                        fleet.write({'rental_check_availability': False})
                    else:
                        fleet.write({'rental_check_availability': True})
                else:
                    fleet.write({'rental_check_availability': True})

    def _get_default_journal(self):
        journal_ids =  self.env['account.move'].with_context(default_type='out_invoice',default_company_id=self.env.user.company_id.id, force_company=self.env.user.company_id.id)._get_default_journal()
        return journal_ids

    image = fields.Binary(related='vehicle_id.image_128', string="Image of Vehicle")
    reserved_fleet_id = fields.Many2one('rental.fleet.reserved', invisible=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    name = fields.Char(string="Name", default="Draft Contract", readonly=True, copy=False)
    customer_id = fields.Many2one('res.partner', required=True, string='Customer', help="Customer")
    vehicle_id = fields.Many2one('fleet.vehicle', string="Vehicle", required=True, help="Vehicle",
                                 readonly=True,
                                 states={'draft': [('readonly', False)]}
                                 )
    car_brand = fields.Many2one('fleet.vehicle.model.brand', string="Fleet Brand", size=50,
                                related='vehicle_id.model_id.brand_id', store=True, readonly=True)
    car_color = fields.Char(string="Fleet Color", size=50, related='vehicle_id.color', store=True, copy=False,
                            default='#FFFFFF', readonly=True)
    cost = fields.Float(string="Rent Cost", help="This fields is to determine the cost of rent", required=True)
    rent_start_date = fields.Date(string="Rent Start Date", required=True, default=str(date.today()),
                                  help="Start date of contract", track_visibility='onchange')
    rent_end_date = fields.Date(string="Rent End Date", required=True, help="End date of contract",
                                track_visibility='onchange')
    state = fields.Selection(
        [('draft', 'Draft'), ('reserved', 'Reserved'), ('running', 'Running'), ('cancel', 'Cancel'),
         ('checking', 'Checking'), ('invoice', 'Invoice'), ('done', 'Done')], string="State",
        default="draft", copy=False, track_visibility='onchange')

    notes = fields.Text(string="Details & Notes")
    cost_generated = fields.Float(string='Recurring Cost',
                                  help="Costs paid at regular intervals, depending on the cost frequency")
    cost_frequency = fields.Selection([('no', 'No'), ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'),
                                       ('yearly', 'Yearly')], string="Recurring Cost Frequency",
                                      help='Frequency of the recurring cost', required=True)
    journal_id = fields.Many2one('account.journal', string='Journal',default=lambda self:self._get_default_journal(),
                                 domain="[('company_id','=', company_id),('type', 'in', ['sale','sale_refund'])]")

    recurring_line = fields.One2many('fleet.rental.line', 'rental_number', readonly=True, help="Recurring Invoices",
                                     copy=False)
    first_payment = fields.Float(string='First Payment',
                                 help="Transaction/Office/Contract charge amount, must paid by customer side other "
                                      "than recurrent payments",
                                 track_visibility='onchange',
                                 required=True)
    first_payment_inv = fields.Many2one('account.move', copy=False)
    first_invoice_created = fields.Boolean(string="First Invoice Created", invisible=True, copy=False)
    attachment_ids = fields.Many2many('ir.attachment', 'car_rent_checklist_ir_attachments_rel',
                                      'rental_id', 'attachment_id', string="Attachments",
                                      help="Images of the vehicle before contract/any attachments")
    checklist_line = fields.One2many('car.rental.checklist', 'checklist_number', string="Checklist",
                                     help="Facilities/Accessories, That should verify when closing the contract.",
                                     states={'invoice': [('readonly', True)],
                                             'done': [('readonly', True)],
                                             'cancel': [('readonly', True)]})
    total = fields.Float(string="Total (Accessories/Tools)", readonly=True, copy=False)
    tools_missing_cost = fields.Float(string="Missing Cost", readonly=True, copy=False,
                                      help='This is the total amount of missing tools/accessories')
    damage_cost = fields.Float(string="Damage Cost", copy=False)
    damage_cost_sub = fields.Float(string="Damage Cost", readonly=True, copy=False)
    total_cost = fields.Float(string="Total", readonly=True, copy=False)
    invoice_count = fields.Integer(compute='_invoice_count', string='# Invoice', copy=False)
    check_verify = fields.Boolean(compute='check_action_verify', copy=False)
    sales_person = fields.Many2one('res.users', string='Sales Person', default=lambda self: self.env.uid,
                                   track_visibility='always')

    def action_run(self):
        for record in self:
            record.state = 'running'

    @api.depends('checklist_line.checklist_active')
    def check_action_verify(self):
        for record in self:
            if record.checklist_line.filtered(lambda c: not c.checklist_active):
                record.check_verify = False
            else:
                record.check_verify = True

    @api.constrains('rent_start_date', 'rent_end_date')
    def validate_rent_dates(self):
        for rec in self:
            if rec.rent_end_date < rec.rent_start_date:
                raise Warning("Please select the valid end date.")

    def set_to_done(self):
        account_move_obj = self.env['account.move']
        for rec in self:
            invoices_payments = account_move_obj.search([('invoice_origin', '=', rec.name),('state','!=','cancel')]).mapped('invoice_payment_state')
            if invoices_payments and ('not_paid' in invoices_payments or 'in_payment' in invoices_payments):
                raise UserError("Some Invoices are pending")
            else:
                rec.state = 'done'

    def _invoice_count(self):
        account_move_obj = self.env['account.move']
        for rec in self:
            rec.invoice_count = account_move_obj.search_count([('invoice_origin', '=', rec.name)])


    @api.constrains('state')
    def state_changer(self):
        if self.state == "running":
            state_id = self.env.ref('fleet_rental.vehicle_state_rent').id
            self.vehicle_id.write({'state_id': state_id})
        elif self.state == "cancel":
            state_id = self.env.ref('fleet_rental.vehicle_state_active').id
            self.vehicle_id.write({'state_id': state_id})
        elif self.state == "invoice":
            self.rent_end_date = fields.Date.today()
            state_id = self.env.ref('fleet_rental.vehicle_state_active').id
            self.vehicle_id.write({'state_id': state_id})

    @api.constrains('checklist_line', 'damage_cost')
    def total_updater(self):
        total = 0.0
        tools_missing_cost = 0.0
        for records in self.checklist_line:
            total += records.price
            if not records.checklist_active:
                tools_missing_cost += records.price
        self.total = total
        self.tools_missing_cost = tools_missing_cost
        self.damage_cost_sub = self.damage_cost
        self.total_cost = tools_missing_cost + self.damage_cost

    def create_fleet_contract_recurring_invoices(self, rent_date):
        inv_obj = self.env['account.move']
        recurring_obj = self.env['fleet.rental.line']
        supplier = self.customer_id

        product_id = self.env['product.product'].search([("name", "=", "Fleet Rental Service")])
        if product_id.property_account_income_id.id:
            income_account = product_id.property_account_income_id
        elif product_id.categ_id.property_account_income_categ_id.id:
            income_account = product_id.categ_id.property_account_income_categ_id
        else:
            raise UserError(
                _('Please define income account for this product: "%s" (id:%d).') % (product_id.name,
                                                                                     product_id.id))
        move_lines = [(0, 0,{
            'name': self.vehicle_id.name,
            'account_id': income_account.id,
            'price_unit': self.cost_generated,
            'quantity': 1,
            'product_id': product_id.id,
        })]
        inv_data = {
            'ref': supplier.name,
            'partner_id': supplier.id,
            'currency_id': self.company_id.currency_id.id,
            'journal_id': self.journal_id.id,
            'invoice_origin': self.name,
            'company_id': self.company_id.id,
            'invoice_date_due': self.rent_end_date,
            'type': 'out_invoice',
            'invoice_line_ids':move_lines
        }
        inv_id = inv_obj.create(inv_data)
        recurring_data = {
            'name': self.vehicle_id.name,
            'date_today': rent_date,
            'account_info': income_account.name,
            'rental_number': self.id,
            'recurring_amount': self.cost_generated,
            'invoice_number': inv_id.id,
            'invoice_ref': inv_id.id,
        }
        recurring_obj.create(recurring_data)

    @api.model
    def fleet_recurring_invoices_scheduler(self):
        inv_obj = self.env['account.move']
        recurring_obj = self.env['fleet.rental.line']
        today = date.today()
        for fleet_contract in self.search([('state','=','running'),('cost_frequency','!=','no')]):
            start_date = datetime.strptime(str(fleet_contract.rent_start_date), '%Y-%m-%d').date()
            end_date = datetime.strptime(str(fleet_contract.rent_end_date), '%Y-%m-%d').date()
            recurring_inv_ids = recurring_obj.search([('date_today','=',today),('rental_number','=',fleet_contract.id),('invoice_ref.state','!=','cancel')])
            if end_date >= date.today() and not recurring_inv_ids:
                temp = 0
                if fleet_contract.cost_frequency == 'daily':
                    temp = 1
                elif fleet_contract.cost_frequency == 'weekly':
                    week_days = (date.today() - start_date).days
                    if week_days % 7 == 0 and week_days != 0:
                        temp = 1
                elif fleet_contract.cost_frequency == 'monthly':
                    if start_date.day == date.today().day and start_date != date.today():
                        temp = 1
                elif fleet_contract.cost_frequency == 'yearly':
                    if start_date.day == date.today().day and start_date.month == date.today().month and \
                            start_date != date.today():
                        temp = 1
                if temp == 1 and fleet_contract.cost_frequency != "no" and fleet_contract.state == "running":
                    supplier = fleet_contract.customer_id
                    product_id = self.env['product.product'].search([("name", "=", "Fleet Rental Service")])
                    if product_id.property_account_income_id.id:
                        income_account = product_id.property_account_income_id
                    elif product_id.categ_id.property_account_income_categ_id.id:
                        income_account = product_id.categ_id.property_account_income_categ_id
                    else:
                        raise UserError(
                            _('Please define income account for this product: "%s" (id:%d).') % (product_id.name,
                                                                                                 product_id.id))

                    move_lines = [(0,0,{
                        'name': fleet_contract.vehicle_id.name,
                        'account_id': income_account.id,
                        'price_unit': fleet_contract.cost_generated,
                        'quantity': 1,
                        'product_id': product_id.id,

                    })]

                    inv_data = {
                        'ref': supplier.name,
                        'partner_id': supplier.id,
                        'currency_id': fleet_contract.company_id.currency_id.id,
                        'journal_id': fleet_contract.journal_id.id,
                        'invoice_origin': fleet_contract.name,
                        'company_id': fleet_contract.company_id.id,
                        'invoice_date_due': self.rent_end_date,
                        'type': 'out_invoice',
                        'invoice_line_ids':move_lines,
                    }
                    inv_id = inv_obj.create(inv_data)

                    recurring_data = {
                        'name': fleet_contract.vehicle_id.name,
                        'date_today': today,
                        'account_info': income_account.name,
                        'rental_number': fleet_contract.id,
                        'recurring_amount': fleet_contract.cost_generated,
                        'invoice_number': inv_id.id,
                        'invoice_ref': inv_id.id,
                    }
                    recurring_obj.create(recurring_data)

            else:
                if self.state == 'running':
                    fleet_contract.state = "checking"

    def action_verify(self):
        self.state = "invoice"
        self.reserved_fleet_id.reserved_vehicle_id.rental_check_availability =  True
        self.reserved_fleet_id.unlink()
        self.rent_end_date = fields.Date.today()
        if self.total_cost > 0:
            inv_obj = self.env['account.move']
            supplier = self.customer_id
            product_id = self.env['product.product'].search([("name", "=", "Fleet Rental Service")])
            if product_id.property_account_income_id.id:
                income_account = product_id.property_account_income_id
            elif product_id.categ_id.property_account_income_categ_id.id:
                income_account = product_id.categ_id.property_account_income_categ_id
            else:
                raise UserError(
                    _('Please define income account for this product: "%s" (id:%d).') % (product_id.name,
                                                                                         product_id.id))
            move_lines = [(0, 0, {
                'name': "Damage/Tools missing cost",
                'account_id': income_account.id,
                'price_unit': self.total_cost,
                'quantity': 1,
                'product_id': product_id.id,
            })]
            inv_data = {
                'ref': supplier.name,
                'partner_id': supplier.id,
                'currency_id': self.company_id.currency_id.id,
                'journal_id': self.journal_id.id,
                'invoice_origin': self.name,
                'company_id': self.company_id.id,
                'invoice_date_due': self.rent_end_date,
                'invoice_line_ids': move_lines
            }
            inv_id = inv_obj.create(inv_data)
            imd = self.env['ir.model.data']
            action = imd.xmlid_to_object('account.view_move_tree')
            list_view_id = self.env.ref('account.view_move_form', False)
            form_view_id = self.env.ref('account.view_move_tree', False)
            result = {
                'domain': "[('id', '=', " + str(inv_id) + ")]",
                'name': 'Fleet Rental Invoices',
                'view_mode': 'form',
                'res_model': 'account.move',
                'type': 'ir.actions.act_window',
                'views': [(list_view_id.id, 'tree'), (form_view_id.id, 'form')],
            }

            if len(inv_id) > 1:
                result['domain'] = "[('id','in',%s)]" % inv_id.ids
            elif len(inv_id) == 1:
                result['views'] = [(form_view_id, 'form')]
                result['res_id'] = inv_id.ids[0]
            else:
                result = {'type': 'ir.actions.act_window_close'}
            return result

    def action_confirm(self):
        check_availability = 0
        for rental_reserved in self.vehicle_id.rental_fleet_reserved_ids:
            if rental_reserved.date_from <= self.rent_start_date <= rental_reserved.date_to:
                check_availability = 1
            elif self.rent_start_date < rental_reserved.date_from:
                if rental_reserved.date_from <= self.rent_end_date <= rental_reserved.date_to:
                    check_availability = 1
                elif self.rent_end_date > rental_reserved.date_to:
                    check_availability = 1
                else:
                    check_availability = 0
            else:
                check_availability = 0
        if check_availability == 0:
            reserved_id = self.vehicle_id.rental_fleet_reserved_ids.create({'customer_id': self.customer_id.id,
                                                                       'date_from': self.rent_start_date,
                                                                       'date_to': self.rent_end_date,
                                                                       'reserved_vehicle_id': self.vehicle_id.id
                                                                       })
            self.write({'reserved_fleet_id': reserved_id.id})
        else:
            raise Warning('Sorry This vehicle is already booked by another customer')
        self.state = "reserved"
        order_date = self.create_date
        order_date = str(order_date)[0:10]
        sequence_id = self.env.ref("fleet_rental.sequence_car_rental").id
        self.name = self.env['ir.sequence'].browse(sequence_id).next_by_id(sequence_date=order_date)

    def action_cancel(self):
        self.state = "cancel"
        invoice_ids = self.env['account.move'].search([('invoice_origin', '=', self.name),('state', '!=', 'cancel')])
        if invoice_ids:
            raise UserError("Some Invoices are pending")
        self.first_invoice_created = False
        if self.reserved_fleet_id:
            self.reserved_fleet_id.reserved_vehicle_id.rental_check_availability = True
            self.reserved_fleet_id.unlink()

    def action_draft(self):
        self.state = "draft"
        if self.reserved_fleet_id:
            self.reserved_fleet_id.reserved_vehicle_id.rental_check_availability = True
            self.reserved_fleet_id.unlink()

    def force_checking(self):
        self.state = "checking"

    def action_view_invoice(self):
        invoice_ids = self.env['account.move'].search([('invoice_origin', '=', self.name)])
        view_id = self.env.ref('account.view_move_form').id
        if invoice_ids:
            if len(invoice_ids) == 1:
                value = {
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'account.move',
                    'view_id': view_id,
                    'type': 'ir.actions.act_window',
                    'name': _('Invoice'),
                    'res_id': invoice_ids.id
                }
            else:
                value = {
                    'domain': str([('id', 'in', invoice_ids.ids)]),
                    'view_type': 'form',
                    'view_mode': 'tree,form',
                    'res_model': 'account.move',
                    'view_id': False,
                    'type': 'ir.actions.act_window',
                    'name': _('Invoice'),
                    'res_id': invoice_ids.ids
                }

            return value

    def action_invoice_create(self):
        recurring_obj = self.env['fleet.rental.line']
        for record in self:
            rent_date = record.rent_start_date
            if record.cost_frequency != 'no' and rent_date < date.today() and record.cost_generated > 0:
                rental_days = (date.today() - rent_date).days
                if record.cost_frequency == 'weekly':
                    rental_days = int(rental_days / 7)
                if record.cost_frequency == 'monthly':
                    rental_days = int(rental_days / 30)
                for rental_day in range(0, rental_days + 1):
                    recurring_inv_ids = recurring_obj.search(
                        [('date_today', '=', rent_date), ('rental_number', '=', record.id),
                         ('invoice_ref.state', '!=', 'cancel')])
                    if rent_date > record.rent_end_date:
                        break
                    if not recurring_inv_ids:
                        record.create_fleet_contract_recurring_invoices(rent_date)
                    if record.cost_frequency == 'daily':
                        rent_date = rent_date + timedelta(days=1)
                    if record.cost_frequency == 'weekly':
                        rent_date = rent_date + timedelta(days=7)
                    if record.cost_frequency == 'monthly':
                        rent_date = rent_date + timedelta(days=30)

        if self.first_payment > 0:
            self.first_invoice_created = True
            inv_obj = self.env['account.move']
            supplier = self.customer_id

            product_id = self.env['product.product'].search([("name", "=", "Fleet Rental Service")])
            if product_id.property_account_income_id.id:
                income_account = product_id.property_account_income_id.id
            elif product_id.categ_id.property_account_income_categ_id.id:
                income_account = product_id.categ_id.property_account_income_categ_id.id
            else:
                raise UserError(
                    _('Please define income account for this product: "%s" (id:%d).') % (product_id.name,
                                                                                         product_id.id))


            move_lines = [(0, 0, {
                'name': self.vehicle_id.name,
                'price_unit': self.first_payment,
                'quantity': 1.0,
                'account_id': income_account,
                'product_id': product_id.id,
            })]
            inv_data = {
                'ref': supplier.name,
                'type': 'out_invoice',
                'partner_id': supplier.id,
                'currency_id': self.company_id.currency_id.id,
                'journal_id': self.journal_id.id,
                'invoice_origin': self.name,
                'company_id': self.company_id.id,
                'invoice_date_due': self.rent_end_date,
                'invoice_line_ids':move_lines
            }
            inv_id = inv_obj.create(inv_data)
            self.first_payment_inv = inv_id.id
            imd = self.env['ir.model.data']
            action = imd.xmlid_to_object('account.action_move_out_invoice_type')
            result = {
                'name': action.name,
                'type': 'ir.actions.act_window',
                'views': [[False, 'form']],
                'target': 'current',
                'res_id': inv_id.id,
                'res_model': 'account.move',
            }
            return result

        else:
            raise Warning("Please enter advance amount to make first payment")


class FleetRentalLine(models.Model):
    _name = 'fleet.rental.line'

    name = fields.Char('Description')
    date_today = fields.Date('Date')
    account_info = fields.Char('Account')
    recurring_amount = fields.Float('Amount')
    rental_number = fields.Many2one('car.rental.contract', string='Rental Number')
    payment_info = fields.Char(compute='paid_info', string='Payment Stage', default='draft')
    invoice_number = fields.Integer(string='Invoice ID')
    invoice_ref = fields.Many2one('account.move', string='Invoice Ref')
    date_due = fields.Date(string='Due Date', related='invoice_ref.invoice_date_due')

    def paid_info(self):
        for record in self:
            if self.env['account.move'].browse(record.invoice_number):
                record.payment_info = self.env['account.move'].browse(record.invoice_number).state
            else:
                record.payment_info = 'Record Deleted'


class CarRentalChecklist(models.Model):
    _name = 'car.rental.checklist'

    name = fields.Many2one('car.tools', string="Name")
    checklist_active = fields.Boolean(string="Available", default=True)
    checklist_number = fields.Many2one('car.rental.contract', string="Checklist Number")
    price = fields.Float(string="Price")

    @api.onchange('name')
    def onchange_name(self):
        self.price = self.name.price


class CarTools(models.Model):
    _name = 'car.tools'

    name = fields.Char(string="Name")
    price = fields.Float(string="Price")
