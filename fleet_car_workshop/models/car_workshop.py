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
from datetime import date
from dateutil.relativedelta import relativedelta
from psutil import long

from odoo.exceptions import UserError
from odoo import models, api, fields, _


class CarWorkshop(models.Model):
    _name = 'car.workshop'
    _description = "Car Workshop"
    _inherit = ['mail.thread']

    def _get_default_vehicle(self):
        car_id = self._context.get('active_id')
        car = self.env['cars.cars'].browse(car_id)
        if car.name:
            return car.name.id
        else:
            return 1



    @api.model
    def _default_company_id(self):
        car_id = self._context.get('active_id')
        car = self.env['cars.cars'].browse(car_id)
        if car.vehicle_id:
            return car.vehicle_id.company_id.id
        else:
            return self.env.company

    def _get_default_partner(self):
        if 'default_vehicle_id' in self.env.context:
            default_vehicle_id = self.env['cars.cars'].browse(self.env.context['default_vehicle_id'])
            return default_vehicle_id.partner_id

    def _get_default_stage_id(self):
        """ Gives default stage_id """
        vehicle_id = self.env.context.get('default_vehicle_id')
        return self.stage_find(vehicle_id, [('fold', '=', False)])

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        search_domain = [('id', 'in', stages.ids)]
        if 'default_vehicle_id' in self.env.context:
            search_domain = ['|', ('vehicle_ids', '=', self.env.context['default_vehicle_id'])] + search_domain

        stage_ids = stages._search(search_domain, order=order)
        return stages.browse(stage_ids)

    name = fields.Char(string='Title', track_visibility='onchange', required=True)
    user_id = fields.Many2one('res.users', string='Assigned to', default=lambda self: self.env.user, tracking=True)
    active = fields.Boolean(string='Active', default=True)
    partner_id = fields.Many2one('res.partner', string='Customer', default=_get_default_partner)
    priority = fields.Selection([('0', 'Normal'), ('1', 'High')], 'Priority', select=True, default='0')
    description = fields.Html(string='Description')
    sequence = fields.Integer(string='Sequence', select=True, default=10,
                              help="Gives the sequence order when displaying a list of tasks.")
    tag_ids = fields.Many2many('workshop.worksheet.tags', string='Tags', ondelete='cascade')
    kanban_state = fields.Selection(
        [('normal', 'In Progress'), ('done', 'Ready for next stage'), ('blocked', 'Blocked')], 'Kanban State',
        help="A task's kanban state indicates special situations affecting it:\n"
             " * Normal is the default situation\n"
             " * Blocked indicates something is preventing the progress of this task\n"
             " * Ready for next stage indicates the task is ready to be pulled to the next stage",
        required=True, track_visibility='onchange', default='normal', copy=False)
    create_date = fields.Datetime(string='Create Date', readonly=True, select=True)
    write_date = fields.Datetime(string='Last Modification Date', readonly=True, select=True)
    date_start = fields.Datetime(string='Starting Date', default=fields.datetime.now(), select=True, copy=False)
    date_end = fields.Datetime(string='Ending Date', select=True, copy=False)
    date_assign = fields.Datetime(string='Assigning Date', select=True, copy=False)
    date_deadline = fields.Datetime(string='Deadline', select=True, copy=False)
    progress = fields.Integer(string="Working Time Progress(%)", copy=False, readonly=True)
    date_last_stage_update = fields.Datetime(string='Last Stage Update', select=True, default=fields.datetime.now(),
                                             copy=False, readonly=True)
    id = fields.Integer('ID', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=_default_company_id)
    color = fields.Integer(string='Color Index')
    vehicle_id = fields.Many2one('cars.cars', string='Vehicle',
                                 default=lambda self: self.env.context.get('default_vehicle_id'), index=True,
                                 tracking=True,
                                 change_default=True)

    stage_id = fields.Many2one('vehicle.worksheet.stages', string='Stage', ondelete='restrict', tracking=True, index=True,
                               default=_get_default_stage_id, group_expand='_read_group_stage_ids',copy=False)
    state = fields.Selection([
        ('waiting', 'Ready'),
        ('workshop_create_invoices', 'Invoiced'),
        ('cancel', 'Invoice Canceled'),
    ], string='Status', readonly=True, default='waiting', track_visibility='onchange', select=True)
    attachment_ids = fields.One2many('ir.attachment', 'res_id', domain=lambda self: [('res_model', '=', self._name)],
                                     auto_join=True, string='Attachments')
    displayed_image_id = fields.Many2one('ir.attachment',
                                         domain="["
                                                "('res_model', '=', 'car.workshop'),"
                                                "('res_id', '=', id),"
                                                "('mimetype', 'ilike', 'image')]",
                                         string='Displayed Image')
    planned_works = fields.One2many('workshop.planned.work', 'work_id', string='Planned/Ordered Works')
    works_done = fields.One2many('workshop.planned.work', 'work_id', string='Work Done', domain=[('completed', '=', True)])
    materials_used = fields.One2many('workshop.material.used', 'material_id', string='Materials Used')
    remaining_hour = fields.Float(string='Remaining Hour', readonly=True, compute="hours_left")
    effective_hour = fields.Float(string='Hours Spent', readonly=True, compute="hours_spent")
    amount_total = fields.Float(string='Total Amount', readonly=True, compute="_compute_amount_total")
    invoice_count = fields.Integer(string="Invoice_count", compute='compute_invoice_count')
    delivery_count = fields.Integer(
        string="Deliveries", compute="_compute_deliveries_count"
    )

    @api.depends('planned_works.work_cost', 'materials_used.price')
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = (sum(record.mapped('planned_works').mapped('work_cost')) + sum(record.mapped('materials_used').mapped('price')))

    def cancel(self):
        for record in self:
            record.state = 'cancel'

    def set_to_ready(self):
        for record in self:
            record.state = 'waiting'

    def workshop_create_invoices(self):
        self.ensure_one()
        journal_id = self.env['ir.config_parameter'].sudo().get_param(
            'fleet_car_workshop.invoice_journal_type')
        if not journal_id:
            raise UserError(_("There is no journal configured for vehicle workshop"))
        customer = self.partner_id
        if not customer.name:
            raise UserError(_('Please select a Customer.'))
        self.state = 'workshop_create_invoices'
        inv_obj = self.env['account.move']

        invoice_line_ids = []
        company_id = self.company_id or self.env.user.company_id
        currency_value = company_id.currency_id.id

        inv_data = {
            'ref': self.name,
            'invoice_partner_bank_id': customer.property_account_receivable_id.id,
            'partner_id': customer.id,
            'currency_id': currency_value,
            'journal_id': int(journal_id),
            'invoice_origin': self.name,
            'company_id': company_id.id,
            'type': 'out_invoice',
            'invoice_partner_bank_id': self.env.user.company_id.partner_id.bank_ids[:1].id,
            'invoice_user_id': self.user_id and self.user_id.id or False,
            'fiscal_position_id': customer.property_account_position_id and customer.property_account_position_id.id or False,

        }

        for records in self.planned_works:
            if records.planned_work.id:
                income_account = records.planned_work.property_account_income_id.id
                inv_line_data = (0, 0, {
                    'name': records.planned_work.name,
                    'account_id': income_account,
                    'price_unit': records.work_cost,
                    'quantity': 1,
                    'product_id': records.planned_work.id,
                })
                invoice_line_ids.append(inv_line_data)
            if not income_account:
                raise UserError(_('There is no income account defined for this product: "%s".') %
                                (records.planned_work.name,))

        for records in self.materials_used:
            if records.material.id:
                income_account = records.material.property_account_income_id.id
                inv_line_data = (0, 0, {
                    'name': records.material.name,
                    'account_id': records.material.property_account_income_id.id,
                    'price_unit': records.price,
                    'quantity': records.amount,
                    'product_id': records.material.id,
                })
                invoice_line_ids.append(inv_line_data)
            if not income_account:
                raise UserError(_('There is no income account defined for this product: "%s".') %
                                (records.material.name,))

        inv_data.update({
            'invoice_line_ids': invoice_line_ids
        })
        inv_id = inv_obj.create(inv_data)
        result = {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'view_mode': 'form',
            'res_model': 'account.move',
            'target': 'current',
            'res_id': inv_id.id,
        }
        IMD = self.env['ir.model.data']
        form_view_id = IMD.xmlid_to_res_id('account.invoice_form')
        if len(inv_id) > 1:
            result['domain'] = "[('id','in',%s)]" % inv_id.ids
        elif len(inv_id) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = inv_id.ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}

        if self.materials_used:
            stock_picking_obj = self.env['stock.picking']
            picking_type_id = self.env['stock.picking.type'].search([('code', '=', 'outgoing'), ('warehouse_id.company_id', '=', company_id.id)],
                               limit=1)
            vals = {
                        'partner_id': self.partner_id.id,
                        'origin': self.name,
                        'car_workshop_id':self.id,
                        'move_type': 'one',
                        'picking_type_id': picking_type_id.id,
                        'location_id': picking_type_id.default_location_src_id.id,
                        'location_dest_id': self.partner_id.property_stock_customer.id,
                    }

            move_lines_list = []
            for product in self.materials_used:
                move_lines_list.append((0, 0, {
                            'name': self.name,
                            'product_id': product.material.id,
                            'product_uom': product.material.uom_id.id,
                            'product_uom_qty': product.amount,
                            'quantity_done': product.amount,
                            'location_id': picking_type_id.default_location_src_id.id,
                            'location_dest_id': self.partner_id.property_stock_customer.id,
                        }))

            vals.update({'move_lines':move_lines_list})
            picking_id = stock_picking_obj.create(vals)
            picking_id.action_confirm()
            picking_id.action_assign()
            picking_id.action_done()
        return result

    def action_view_delivery(self):
        delivery = self.env["stock.picking"].search(
            [("car_workshop_id", "=", self.id), ("picking_type_code", "=", "outgoing")]
        )
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action['context'] = {'create': False}

        if len(delivery) > 1:
            action["domain"] = [("id", "in", delivery.ids)]
        elif len(delivery) == 1:
            form_view = [(self.env.ref("stock.view_picking_form").id, "form")]
            if "views" in action:
                action["views"] = form_view + [
                    (state, view) for state, view in action["views"] if view != "form"
                ]
            else:
                action["views"] = form_view
            action["res_id"] = delivery.id
        else:
            action = {"type": "ir.actions.act_window_close"}
        return action

    def _compute_deliveries_count(self):
        for record in self:
            delivery_count = self.env["stock.picking"].search_count(
                [
                    ("car_workshop_id", "=", record.id),
                    ("picking_type_code", "=", "outgoing"),
                ]
            )
            record.delivery_count = delivery_count



    @api.depends('works_done.duration')
    def hours_spent(self):
        for record in self:
            record.effective_hour = sum(record.mapped('works_done').mapped('duration'))

    @api.depends('planned_works.time_spent')
    def hours_left(self):
        for record in self:
            record.remaining_hour = sum(record.mapped('planned_works').mapped('time_spent')) - record.effective_hour


    @api.constrains('date_assign', 'date_deadline')
    def update_wworkshop_worked_time_progress(self):
        for rec in self:
            if not rec.stage_id.is_final_stage and not rec.stage_id.is_cancelled_stage:
                end_date = fields.Datetime.from_string(rec.date_deadline)
                start_date = fields.Datetime.from_string(rec.date_assign)
                current_date = fields.Datetime.from_string(fields.Datetime.now())
                if rec.date_deadline and rec.date_assign and end_date > start_date:
                    if current_date < end_date:
                        diff1 = relativedelta(end_date, start_date)
                        if diff1.days == 0:
                            total_hr = int(diff1.minutes)
                        else:
                            total_hr = int(diff1.days) * 24 * 60 + int(diff1.minutes)
                        diff2 = relativedelta(current_date, start_date)
                        if diff2.days == 0:
                            current_hr = int(diff2.minutes)
                        else:
                            current_hr = int(diff2.days) * 24 * 60 + int(diff2.minutes)
                        if total_hr != 0:
                            rec.progress = ((current_hr * 100) / total_hr)
                        else:
                            rec.progress = 100
                    else:
                        rec.progress = 100
                else:
                    rec.progress = 0

    @api.model
    def _track_subtype(self, init_values):
        record = self.ensure_one()
        if 'kanban_state' in init_values and record.kanban_state == 'blocked':
            return self.env.ref('fleet_car_workshop.mt_task_blocked')
        elif 'kanban_state' in init_values and record.kanban_state == 'done':
            return self.env.ref('fleet_car_workshop.mt_task_ready')
        elif 'user_id' in init_values and record.user_id:  # assigned -> new
            return self.env.ref('fleet_car_workshop.mt_task_new')
        elif 'stage_id' in init_values and record.stage_id and record.stage_id.sequence <= 1:  # start stage -> new
            self.env.ref('fleet_car_workshop.mt_task_new')
        elif 'stage_id' in init_values:
            return self.env.ref('fleet_car_workshop.mt_task_stages')
        return super(CarWorkshop, self)._track_subtype(init_values)
    @api.model
    def create(self, vals):
        # context: no_log, because subtype already handle this
        context = dict(self.env.context, mail_create_nolog=True)

        # for default stage
        if vals.get('vehicle_id') and not context.get('default_vehicle_id'):
            context['default_vehicle_id'] = vals.get('vehicle_id')
        # user_id change: update date_assign
        if vals.get('user_id'):
            vals['date_assign'] = fields.Datetime.now()
        # Stage change: Update date_end if folded stage and date_last_stage_update
        if vals.get('stage_id'):
            vals.update(self.change_date_end(vals['stage_id']))
            vals['date_last_stage_update'] = fields.Datetime.now()
        task = super(CarWorkshop, self.with_context(context)).create(vals)
        return task

    def write(self, vals):
        now = fields.Datetime.now(self)
        # stage change: update date_last_stage_update
        if 'stage_id' in vals:
            vals.update(self.change_date_end(vals['stage_id']))
            vals['date_last_stage_update'] = now
            # reset kanban state when changing stage
            if 'kanban_state' not in vals:
                vals['kanban_state'] = 'normal'
        # user_id change: update date_assign
        if vals.get('user_id') and 'date_assign' not in vals:
            vals['date_assign'] = now
        result = super(CarWorkshop, self).write(vals)
        return result

    def change_date_end(self, stage_id):
        worksheet_stage = self.env['vehicle.worksheet.stages'].browse(stage_id)
        if worksheet_stage.fold:
            return {'date_end': fields.Datetime.now()}
        return {'date_end': False}

    @api.onchange('vehicle_id')
    def onchange_vehicle(self):
        if self.vehicle_id.exists():
            self.partner_id = self.vehicle_id.partner_id

    def stage_find(self, vehicle_id, domain=[], order='sequence'):
        """ Override of the base.stage method
            Parameter of the stage search taken from the lead:
            - vehicle_id: if set, stages must belong to this section or
              be a default stage; if not set, stages must be default
              stages
        """
        # collect all vehicle_ids
        vehicle_ids = []
        if vehicle_ids:
            vehicle_ids.append(vehicle_id)
        vehicle_ids.extend(self.mapped('vehicle_id').ids)
        search_domain = []
        if vehicle_ids:
            search_domain = [('|')] * (len(vehicle_ids) - 1)
            for vehicle in vehicle_ids:
                if isinstance(vehicle, (int, long)):
                    search_domain.append(('vehicle_ids', '=', vehicle))
        search_domain += list(domain)
        # perform search, return the first found
        stage_ids = self.env['vehicle.worksheet.stages'].search(search_domain, order=order, limit=1).id
        if stage_ids:
            return stage_ids
        return False

    def get_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoices',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'res_model': 'account.move',
            'domain': [('invoice_origin', '=', self.name)],
            'context': "{'create': False}"
        }

    def compute_invoice_count(self):
        account_move_obj = self.env['account.move']
        for record in self:
            record.invoice_count = account_move_obj.search_count(
                [('invoice_origin', '=', self.name)])
