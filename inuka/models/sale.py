# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


import base64
import io
import csv
from datetime import date
from dateutil.relativedelta import relativedelta
from lxml import etree
from odoo.osv.orm import setup_modifiers
from datetime import datetime, date
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def default_get(self, fields):
        res = super(SaleOrder, self).default_get(fields)
        user_group_ids = self.env['res.users'].browse(self._uid).groups_id.ids
        pos_group_id = self.env.ref('inuka.pos_users').id
        if pos_group_id in user_group_ids:
            warehouse_id = self.env['stock.warehouse'].search([('name', '=', 'Bellpark')])
#             team_id = self.env['crm.team'].search([('name', '=', 'Point of Sale')], limit=1, order="id desc")
            res.update({'order_sent_by': 'inuka',
                        'warehouse_id': warehouse_id.id if warehouse_id else False,
#                         'team_id': team_id.id if team_id else False,
                        'channel': 'front'})
        else:
            warehouse_id = self.env['stock.warehouse'].search([('name', '=', '8 Vrede Street')])
#             team_id = self.env['crm.team'].search([('name', '=', 'Sales')], limit=1, order="id desc")
            res.update({'order_sent_by': 'inuka',
                        'warehouse_id': warehouse_id.id if warehouse_id else False,
#                         'team_id': team_id.id if team_id else False,
                        'channel': 'admin'})
        return res

#     @api.multi
#     @api.onchange('partner_id')
#     def onchange_partner_id(self):
#         res = super(SaleOrder, self).onchange_partner_id()
#         if self.partner_id:
#             user_group_ids = self.env['res.users'].browse(self._uid).groups_id.ids
#             pos_group_id = self.env.ref('inuka.pos_users').id
#             if pos_group_id in user_group_ids:
#                 team_id = self.env['crm.team'].search([('name', '=', 'Point of Sale')], limit=1, order="id desc")
#             else:
#                 team_id = self.env['crm.team'].search([('name', '=', 'Sales')], limit=1, order="id desc")
#             self.update({'team_id': team_id.id if team_id else False})
#         return res

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False,
                        submenu=False):
        ctx = self.env.context.copy()
        ctx.update({'group_change_unit_prices': self.env.user.has_group('inuka.change_unit_prices')})
        res = super(SaleOrder, self.with_context(ctx)).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar,
            submenu=submenu)
        if view_type == 'search':
            doc = etree.XML(res['arch'])
            search_name_last_month = False
            search_name_inuka_month = False
            date_today = date.today().strftime('%d')
            if int(date_today) in [x for x in range(1, 8)]:
                search_name_last_month = "//filter[@name='last_month']"
                search_name_inuka_month = "//filter[@name='inuka_month']"
            else:
                search_name_last_month = "//filter[@name='last_month_1_7']"
                search_name_inuka_month = "//filter[@name='inuka_month_1_7']"
            if search_name_last_month:
                nodes = doc.xpath(search_name_last_month)
                for node in nodes:
                    node.set('invisible', '1')
                    setup_modifiers(node)
            if search_name_inuka_month:
                nodes = doc.xpath(search_name_inuka_month)
                for node in nodes:
                    node.set('invisible', '1')
                    setup_modifiers(node)
            res['arch'] = etree.tostring(doc)
        return res


    def _default_expiry_date(self):
        return date.today() + relativedelta(days=90)

    @api.model
    def _get_default_team(self):
        return self.env['crm.team']._get_default_team_id() or self.env['crm.team'].search(
            [('company_id', '=', self.env.user.company_id.id)], limit=1)

    @api.depends('order_line', 'order_line.pv')
    def _compute_tot_pv(self):
        for order in self:
            tot_pvs = 0.0
            for line in order.order_line:
                tot_pvs += line.pv
            order.total_pv = tot_pvs

    order_sent_by = fields.Selection([
        ('email', 'Email'),
        ('facebook', 'Facebook'),
        ('fax', 'Fax'),
        ('inuka', 'Inuka'),
        ('phone', 'Phone'),
        ('sms', 'SMS'),
        ('whatsapp', 'Whatsapp'),
        ('portal', 'Portal')],
        string="Order Sent By", default="email", readonly=True,
        states={'draft': [('readonly', False)], 'sent': [('readonly', False)]})
    order_type = fields.Selection([
        ('collect', 'Collect / No Shipping'),
        ('bulk', 'Part of Bulk'),
        ('consolidated', 'Consolidated'),
        ('single', 'Single'),
        ('upfront', 'Upfront'),
        ('stock', 'Stock (for Up front)')],
        string='Order Type', default="collect", readonly=True,
        states={'draft': [('readonly', False)], 'sent': [('readonly', False)]})
    sale_date = fields.Date('Sale Date', readonly=True, default=fields.Date.context_today,
                            states={'draft': [('readonly', False)], 'sent': [('readonly', False)]})
    order_total = fields.Float('Order Total', readonly=True,
                               states={'draft': [('readonly', False)], 'sent': [('readonly', False)]})
    product_cost = fields.Float('Product Cost', readonly=True,
                                states={'draft': [('readonly', False)], 'sent': [('readonly', False)]})
    shipping_cost = fields.Float('Shipping Cost', readonly=True,
                                 states={'draft': [('readonly', False)], 'sent': [('readonly', False)]})
    pv = fields.Float('PV', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]})
    total_pv = fields.Float(compute='_compute_tot_pv', store=True)
    #     has_invoice = fields.Boolean(string="Has Invoice", compute="_compute_has_invoice", store=True)
    reserve = fields.Monetary(string='Available Funds', compute="_compute_reserve")
    paid = fields.Boolean(readonly=True, copy=False)
    order_status = fields.Selection([
        ('new', 'New Order'),
        ('open', 'Open'),
        ('general', 'Snag General'),
        ('payment', 'Snag Payment Option'),
        ('unreadable', 'Snag Unreadable')
    ], string="Order Status", default="new", readonly=True,
        states={'draft': [('readonly', False)], 'sent': [('readonly', False)]})
    delivery_status = fields.Selection([
        ('to_deliver', 'To Deliver'),
        ('partially', 'Partially Delivered'),
        ('fully', 'Fully Delivered'),
    ], compute="_compute_delivery_status", string="Delivery Status", store=True)
    bulk_master_id = fields.Many2one("bulk.master", string="Bulk")
#     states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}
    bulk_lock = fields.Boolean('Bulk Lock', related="bulk_master_id.bulk_lock", store=True)
    kit_order = fields.Boolean("Kit Order", readonly=True)
    validity_date = fields.Date(string='Expiration Date', readonly=True, copy=False,
                                states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
                                help="Manually set the expiration date of your quotation (offer), or it will set the date automatically based on the template if online quotation is installed.",
                                default=_default_expiry_date)
    channel = fields.Selection([
        ('front', 'Front Office'),
        ('admin', 'Admin'),
        ('portal', 'Online Portal'),
        ('mobile', 'Mobile Application'),
    ], string="Channel")
    team_id = fields.Many2one('crm.team', 'Sales Team', change_default=True, default=_get_default_team,
                              oldname='section_id')
    member_status = fields.Selection([
        ('candidate', 'Candidate'),
        ('new', 'New'),
        ('junior', 'Junior'),
        ('senior', 'Senior'),
        ('pearl', 'Pearl'),
        ('ruby', 'Ruby'),
        ('emerald', 'Emerald'),
        ('sapphire', 'Sapphire'),
        ('diamond', 'Diamond'),
        ('double_diamond', 'Double Diamond'),
        ('triple_diamond', 'Triple Diamond'),
        ('exective_diamond', 'Exective Diamond'),
        ('presidential', 'Presidential'),
        ('cancelled', 'Cancelled'),
        ('discontinued', 'Discontinued')
        ], string='Member Status', related="partner_id.status", track_visibility='onchange')
    sale_order_count = fields.Integer(compute="_compute_sale_order_count")

    def _compute_sale_order_count(self):
        for order in self:
            order.sale_order_count = len(self.sudo().search([('partner_id', '=', order.partner_id.id), ('state', '=', 'sale'), ('delivery_status', '=', 'to_deliver')]) - order)

    @api.multi
    def view_sale_orders(self):
        self.ensure_one()
        orders = self.sudo().search([('partner_id', '=', self.partner_id.id), ('state', '=', 'sale'), ('delivery_status', '=', 'to_deliver')]) - self
        action = self.env.ref('sale.action_orders').read()[0]
        action['domain'] = [('id', 'in', orders.ids)]
        return action

    @api.depends('state', 'order_line', 'order_line.qty_delivered', 'order_line.product_uom_qty')
    def _compute_delivery_status(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for order in self:
            if order.state not in ('sale', 'done'):
                order.delivery_status = 'to_deliver'
                continue

            if all(float_compare(line.qty_delivered, 0.000, precision_digits=precision) == 0 for line in
                   order.order_line if line.product_uom_qty):
                order.delivery_status = 'to_deliver'
            elif all(
                    float_compare(line.qty_delivered, line.product_uom_qty, precision_digits=precision) == 0 for line in
                    order.order_line if line.product_id.type != 'service'):
                order.delivery_status = 'fully'
            else:
                order.delivery_status = 'partially'

    def _compute_reserve(self):
        for order in self:
            res_funds = self.env['reserved.fund'].search([('customer_id', '=', order.partner_id.id)])
            amount_reserve = sum([x.amount for x in res_funds])
            order.reserve = -(
                    order.partner_id.credit - order.partner_id.debit) + order.partner_id.credit_limit - amount_reserve

    @api.onchange('order_type')
    def _onchange_bulk_master_id(self):
        if self.order_type:
            self.bulk_master_id = False

    #     @api.onchange('partner_id')
    #     def onchange_partner_id(self):
    #         super(SaleOrder, self).onchange_partner_id()
    #         self.partner_shipping_id = False

    @api.model
    def create(self, vals):
        context = dict(self.env.context or {})
        partner_id = vals.get('partner_id')
        status = self.env['res.partner'].browse(partner_id).status
        if not context.get('kit_order') and status == 'candidate':
            raise UserError(_("You cannot create an order for a Candidate."))
        channel = self.env['mail.channel'].search([('name', 'like', 'Escalations')], limit=1)
        res = super(SaleOrder, self).create(vals)
        if res.partner_id.mobile:
            sms_template = self.env.ref('sms_frame.sms_template_inuka_international')
            msg_compose = self.env['sms.compose'].create({
                'record_id': res.id,
                'model': 'sale.order',
                'sms_template_id': sms_template.id,
                'from_mobile_id': self.env.ref('sms_frame.sms_number_inuka_international').id,
                'to_number': res.partner_id.mobile,
                'sms_content': """ INUKA thanks you for your order %s, an SMS with details will follow when your order (Ref: %s) is dispatched^More info on 27219499850""" % (
                    res.partner_id.name, res.name)
            })
            msg_compose.send_entity()
        if res.partner_id.watchlist and channel:
            res.message_subscribe(channel_ids=[channel.id])
        return res

    @api.model
    def search(self, args, offset=False, limit=None, order=None, count=False):
        previous_date = fields.Datetime.to_string(date.today() + relativedelta(months=-3))  # Getting 3 month before date
        if not self.user_has_groups("account.group_account_user, account.group_account_manager"):
            args += [('create_date', '>=', previous_date)]
        return super(SaleOrder, self).search(args=args, offset=offset, limit=limit, order=order, count=count)

    @api.multi
    def dummy_redirect(self):
        return

    @api.multi
    def action_confirm(self):
        ReservedFund = self.env['reserved.fund']
        for order in self:
            reserved_fund = ReservedFund.search([('order_id', '=', order.id)], limit=1)
            already_reserved = reserved_fund.amount
            order_total = max(order.amount_total, order.order_total)
            if reserved_fund and already_reserved < order_total:
                raise UserError(_('The Order Total amount does not match the reserved funds amount, please unreserve and reserve funds again to continue.'))
            if already_reserved > order_total:
                reserved_fund.write({'amount': order_total})
            if order.carrier_id.blocked_for_delivery:
                raise UserError(
                    _("Delivery Method not allowed. Please select a different delivery method to continue."))
            res = order.carrier_id.rate_shipment(order)
            order.get_delivery_price()
            order.set_delivery_line()
            if order.channel == 'portal':
                if (order.reserve + order.order_total) - order.amount_total < 0:
                    raise UserError(_("Insufficient Funds Available."))
                else:
                    reserve = (order.reserve + order.order_total) - order.amount_total
                    ReservedFund.create({
                        'date': fields.Datetime.now(),
                        'desctiption': 'Reservation for %s for Order %s for an amount of %d by %s' % (
                            order.partner_id.name, order.name, order.order_total, order.user_id.name),
                        'amount': (order.amount_total - order.order_total),
                        'order_id': order.id,
                        'customer_id': order.partner_id.id,
                    })
            order.write({'shipping_cost': res['price'], 'pv': order.total_pv, 'order_total': order.amount_total})
            order.picking_ids.write({'bulk_master_id': order.bulk_master_id.id})
        return super(SaleOrder, self).action_confirm()

    @api.multi
    def action_cancel(self):
        super(SaleOrder, self).action_cancel()
        self.action_unlink_reserved_fund()
        for order in self:
            if order.order_type in ('bulk', 'consolidated'):
                self.write({'bulk_master_id': False})

    @api.multi
    def action_add_reserved_fund(self):
        ReservedFund = self.env['reserved.fund']
        for order in self:
            if order.order_line:
                order.get_delivery_price()
                order.set_delivery_line()
                order_total = max(order.amount_total,order.order_total)
                if order.reserve >= order_total:
                    resv_id = ReservedFund.create({
                        'date': fields.Datetime.now(),
                        'desctiption': 'Reservation for %s for Order %s for an amount of %d by %s' % (
                            order.partner_id.name, order.name, order_total, order.user_id.name),
                        'amount': order_total,
                        'order_id': order.id,
                        'customer_id': order.partner_id.id,
                    })
                    order.paid = True
                    msg = "<b>Fund Reserved</b><ul>"
                    msg += "<li>Reservation for %s <br/> for Order %s for an amount of <br/> %s %d by %s" % (
                        order.partner_id.name, order.name, order.company_id.currency_id.symbol, order_total,
                        order.user_id.name)
                    msg += "</ul>"
                    order.message_post(body=msg)
                else:
                    raise UserError(_('Insufficient Funds Available'))

    @api.multi
    def action_unlink_reserved_fund(self):
        ReservedFund = self.env['reserved.fund']
        for order in self:
            res_funds = ReservedFund.search([('order_id', '=', order.id)])
            # res_funds.unlink()
            res_funds.write({
                'active': False,
            })
            order.paid = False
            msg = "<b>Fund unreserved</b><ul>"
            msg += "<li>Reservation Reversed for %s <br/> for Order %s for an amount of <br/> %s %d by %s" % (
                order.partner_id.name, order.name, order.company_id.currency_id.symbol, order.order_total,
                order.user_id.name)
            msg += "</ul>"
            order.message_post(body=msg)

    @api.multi
    def _prepare_invoice(self):
        res = super(SaleOrder, self)._prepare_invoice()
        res['sale_date'] = self.sale_date
        res['channel'] = self.channel
        res['kit_order'] = self.kit_order
        return res

    @api.multi
    def action_account_invoice_payment_so(self):
        action = self.env.ref('account.action_account_invoice_payment').read()[0]
        self.get_delivery_price()
        self.set_delivery_line()
        action['context'] = {'from_so_register_payment': True,
                             'default_amount': self.amount_total,
                             'default_communication': self.name,
                             'default_payment_type': 'inbound',
                             'default_partner_type': 'customer',
                             'default_partner_id': self.partner_id.id}
        return action


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    pv = fields.Float("PV's")
    unit_pv = fields.Float("Unit PV")

    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        super(SaleOrderLine, self).product_id_change()
        self.pv = 0 if self.discount > 0 else self.product_id.pv * self.product_uom_qty
        self.unit_pv = 0 if self.discount > 0 else self.product_id.pv

    @api.onchange('product_uom_qty')
    def _onchange_product_uom_qty(self):
        self.pv = 0 if self.discount > 0 else self.product_id.pv * self.product_uom_qty

    @api.onchange('discount')
    def _set_pv_zero(self):
        if self.discount > 0:
            self.pv = 0
            self.unit_pv = 0
        else:
            self.pv = self.product_id.pv * self.product_uom_qty
            self.unit_pv = self.product_id.pv


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    advance_payment_method = fields.Selection(default='delivered')


class ReservedFund(models.Model):
    """Master should be added which will be used to reserve funds on a quotation"""
    _name = "reserved.fund"
    _description = "Reserved Fund"
    _rec_name = 'order_id'

    date = fields.Datetime(readonly=True, requied=True, default=lambda self: fields.Datetime.now())
    desctiption = fields.Char(readonly=True, requied=True)
    amount = fields.Float(readonly=True, requied=True)
    order_id = fields.Many2one('sale.order', readonly=True, requied=True)
    customer_id = fields.Many2one('res.partner', readonly=True, requied=True)
    active = fields.Boolean(default=True, readonly=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)


class SaleUpload(models.Model):
    _name = "sale.upload"
    _description = "Sale Upload"

    name = fields.Char("Name")
    state = fields.Selection([
        ('new', 'New'),
        ('inprogress', 'In Progress'),
        ('completed', 'Completed'),
        ('error', 'Error'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='new')
    start_time = fields.Datetime("Start Time")
    end_time = fields.Datetime("End Time")
    duration = fields.Integer(compute="_compute_duration", string="Duration")
    result = fields.Text()
    file = fields.Binary()
    end_point = fields.Integer("End Point")
    batch_size = fields.Integer("Batch Size")

    def _compute_duration(self):
        for record in self:
            start_time = fields.Datetime.from_string(record.start_time)
            end_time = fields.Datetime.from_string(record.end_time)
            duration = 0
            if start_time and end_time:
                duration = (end_time - start_time).total_seconds()
            record.duration = duration

    @api.model
    def run(self):
        record = self.search([('state', 'in', ('new', 'inprogress'))], limit=1, order="create_date")
        if record:
            record.button_start()

    @api.multi
    def button_start(self):
        self.ensure_one()
        self.state = 'inprogress'
        self.start_time = fields.Datetime.now(self)
        self.import_data()
        return True

    @api.multi
    def button_cancel(self):
        self.ensure_one()
        self.state = 'cancelled'
        return True

    @api.multi
    def import_data(self):
        self.ensure_one()
        row_list = []

        try:
            data = base64.b64decode(self.file)
            file_input = io.StringIO(data.decode("utf-8"))
            file_input.seek(0)
            reader = csv.reader(file_input, delimiter=',', lineterminator='\r\n')
            reader_info = []
            reader_info.extend(reader)
            keys = reader_info.pop(0)
        except Exception as e:
            raise UserError(
                _("Invalid file. \n Note: file must be csv" % tools.ustr(e)))

        if self.end_point == 0:
            start_point = 0
            end_point = start_point + self.batch_size
        else:
            start_point = self.end_point
            end_point = start_point + self.batch_size

        if end_point >= len(reader_info):
            end_point = len(reader_info)

        status_dict = {
            'Candidate': 'candidate',
            'New': 'new',
            'Junior': 'junior',
            'Senior': 'senior',
            'Pearl': 'pearl',
            'Ruby': 'ruby',
            'Emerald': 'emerald',
            'Sapphire': 'sapphire',
            'Diamond': 'diamond',
            'Double Diamond': 'double_diamond',
            'Triple Diamond': 'triple_diamond',
            'Exective Diamond': 'exective_diamond',
            'Presidential': 'presidential',
            'Cancelled': 'cancelled',
            'Discontinued': 'discontinued',
        }

        for row in range(start_point, end_point):
            field = reader_info[row]
            values = dict(zip(keys, field))
            if values.get('MEMBERID') and values.get('STATUS') and values.get('SALESMONTH') and values.get('SALESYEAR'):
                if values.get('STATUS') in status_dict.keys() or values.get('STATUS') == '#N/A':
                    row_list.append(values)

        month_dict = {
            '1': 'jun',
            '2': 'jul',
            '3': 'aug',
            '4': 'sep',
            '5': 'oct',
            '6': 'nov',
            '7': 'dec',
            '8': 'jan',
            '9': 'feb',
            '10': 'mar',
            '11': 'apr',
            '12': 'may'
        }

        quarter_dict = {
            '1': 'q1',
            '2': 'q1',
            '3': 'q1',
            '4': 'q2',
            '5': 'q2',
            '6': 'q2',
            '7': 'q3',
            '8': 'q3',
            '9': 'q3',
            '10': 'q4',
            '11': 'q4',
            '12': 'q4'
        }

        record_count = status_count = 0
        for data in row_list:
            ref = data.get('MEMBERID')
            try:
                sql_query = """UPDATE res_partner
                               SET
                               personal_pv = %s, pv_downline_1 = %s,
                               pv_downline_2 = %s, pv_downline_3 = %s,
                               pv_downline_4 = %s, pv_tot_group = %s,
                               personal_members = %s, new_members = %s
                               WHERE ref = %s
                               RETURNING id, status;"""

                params = (
                    data.get('PVPERS') or 0.0,
                    data.get('PVDOWNLINE1') or 0.0,
                    data.get('PVDOWNLINE2') or 0.0,
                    data.get('PVDOWNLINE3') or 0.0,
                    data.get('PVDOWNLINE4') or 0.0,
                    data.get('PVTOTGROUP') or 0.0,
                    data.get('ACTIVEPERSMEM') or 0,
                    data.get('PERSNEWMEM') or 0,
                    ref,
                )
                self.env.cr.execute(sql_query, params)
                results = self.env.cr.fetchall()

                sql_ph_query = """SELECT id FROM performance_history
                                 WHERE partner_id = (SELECT id FROM res_partner WHERE ref = %s) and
                                 months = %s and years = %s"""
                ph_params = (
                    ref,
                    month_dict.get(data.get('SALESMONTH')),
                    data.get('SALESYEAR'),
                )
                self.env.cr.execute(sql_ph_query, ph_params)
                ph_result = self.env.cr.fetchone()

                sql_select_query = """SELECT id FROM res_partner WHERE ref = %s"""
                select_params = (
                    ref,
                )
                self.env.cr.execute(sql_select_query, select_params)
                partner_result = self.env.cr.fetchone()
                if not ph_result:
                    if partner_result:
                        sql_insert_query = """INSERT INTO performance_history (partner_id, performance_type, "date", months, quarters, years,
                                            status, personal_pv, pv_downline_1, pv_downline_2, pv_downline_3, pv_downline_4, pv_tot_group,
                                            personal_members, new_members) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                            """
                        insert_params = (
                            partner_result and partner_result[0],
                            'month',
                            fields.date.today(),
                            month_dict.get(data.get('SALESMONTH')),
                            quarter_dict.get(data.get('SALESMONTH')),
                            data.get('SALESYEAR'),
                            'discontinued' if data.get('STATUS') == '#N/A' else status_dict.get(data.get('STATUS')),
#                             status_dict.get(data.get('STATUS')) if data.get('STATUS') in status_dict.keys() else 'discontinued',
                            data.get('PVPERS'),
                            data.get('PVDOWNLINE1'),
                            data.get('PVDOWNLINE2'),
                            data.get('PVDOWNLINE3'),
                            data.get('PVDOWNLINE4'),
                            data.get('PVTOTGROUP'),
                            data.get('ACTIVEPERSMEM'),
                            data.get('PERSNEWMEM'),
                        )
                        self.env.cr.execute(sql_insert_query, insert_params)
                else:
                    sql_update_query = """UPDATE performance_history SET partner_id = %s, performance_type = %s, "date" = %s,
                                        months = %s, quarters = %s, years = %s, status = %s,personal_pv = %s, pv_downline_1 = %s,
                                        pv_downline_2 = %s, pv_downline_3 = %s, pv_downline_4 = %s, pv_tot_group = %s,
                                        personal_members = %s, new_members = %s WHERE id = %s
                                        """
                    update_params = (
                        partner_result and partner_result[0],
                        'month',
                        fields.date.today(),
                        month_dict.get(data.get('SALESMONTH')),
                        quarter_dict.get(data.get('SALESMONTH')),
                        data.get('SALESYEAR'),
#                         status_dict.get(data.get('STATUS')) if data.get('STATUS') in status_dict.keys() else 'discontinued',
                        'discontinued' if data.get('STATUS') == '#N/A' else status_dict.get(data.get('STATUS')),
                        data.get('PVPERS'),
                        data.get('PVDOWNLINE1'),
                        data.get('PVDOWNLINE2'),
                        data.get('PVDOWNLINE3'),
                        data.get('PVDOWNLINE4'),
                        data.get('PVTOTGROUP'),
                        data.get('ACTIVEPERSMEM'),
                        data.get('PERSNEWMEM'),
                        ph_result and ph_result[0]
                    )

                    self.env.cr.execute(sql_update_query, update_params)
                if not results:
                    continue

                record_count += 1

                partner_id = results[0][0]
                old_status = results[0][1]
                new_status = status_dict.get(data.get('STATUS')) if data.get('STATUS') in status_dict.keys() else 'discontinued',
                if old_status != new_status[0] and (old_status or (new_status and new_status[0])):
                    sql_query = """INSERT INTO sale_upload_intermediate
                                   (partner_id, old_status, new_status, active)
                                   VALUES (%s, %s, %s, %s);"""

                    params = (partner_id, old_status, new_status[0], True)

                    self.env.cr.execute(sql_query, params)

                    status_count += 1
            except Exception as e:
                result = 'Error: %s' % (str(e))
                self.write({
                    'result': result,
                    'end_time': fields.Datetime.now(self),
                    'state': 'error'
                })
                return True

        self.env.cr.commit()

        result = '%s - %s: %s records updated, %s status change updated' % (
            start_point, end_point, record_count, status_count)

        if self.result:
            result = self.result + '\n' + result

        if end_point == len(reader_info):
            self.write({
                'result': result,
                'end_time': fields.Datetime.now(self),
                'state': 'completed'
            })
        else:
            self.write({
                'end_point': end_point,
                'result': result,
                'end_time': fields.Datetime.now(self),
                'state': 'inprogress'
            })

        return True


class SaleUploadIntermediate(models.Model):
    _name = "sale.upload.intermediate"
    _description = "Sale Upload Intermediate"
    _rec_name = 'partner_id'

    partner_id = fields.Many2one("res.partner", string="Customer")
    old_status = fields.Selection([
        ('candidate', 'Candidate'),
        ('new', 'New'),
        ('junior', 'Junior'),
        ('senior', 'Senior'),
        ('pearl', 'Pearl'),
        ('ruby', 'Ruby'),
        ('emerald', 'Emerald'),
        ('sapphire', 'Sapphire'),
        ('diamond', 'Diamond'),
        ('double_diamond', 'Double Diamond'),
        ('triple_diamond', 'Triple Diamond'),
        ('exective_diamond', 'Exective Diamond'),
        ('presidential', 'Presidential'),
        ('cancelled', 'Cancelled'),
        ('discontinued', 'Discontinued'),
    ], string='Old Status')
    new_status = fields.Selection([
        ('candidate', 'Candidate'),
        ('new', 'New'),
        ('junior', 'Junior'),
        ('senior', 'Senior'),
        ('pearl', 'Pearl'),
        ('ruby', 'Ruby'),
        ('emerald', 'Emerald'),
        ('sapphire', 'Sapphire'),
        ('diamond', 'Diamond'),
        ('double_diamond', 'Double Diamond'),
        ('triple_diamond', 'Triple Diamond'),
        ('exective_diamond', 'Exective Diamond'),
        ('presidential', 'Presidential'),
        ('cancelled', 'Cancelled'),
        ('discontinued', 'Discontinued'),
    ], string='New Status')
    active = fields.Boolean(default=True)

    @api.model
    def update_status(self):
        records = self.search([], limit=200)
        for record in records:
            record.partner_id.write({'status': record.new_status})
            record.write({'active': False})


class Lead(models.Model):
    _inherit = "crm.lead"

    team_id = fields.Many2one('crm.team', string='Sales Team', oldname='section_id',
                              default=lambda self: self.env['crm.team'].sudo()._get_default_team_id(
                                  user_id=self.env.uid),
                              index=True, track_visibility='onchange',
                              help='When sending mails, the default email address is taken from the sales channel.')


class SaleReport(models.Model):
    _inherit = "sale.report"

    team_id = fields.Many2one('crm.team', 'Sales Team', readonly=True, oldname='section_id')
