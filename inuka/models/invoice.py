# -*- coding: utf-8 -*-

import json
from datetime import date
from dateutil.relativedelta import relativedelta
from lxml import etree

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero
from odoo.osv.orm import setup_modifiers


class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    @api.multi
    def action_unlink_reserved_fund(self):
        sale_order_id = self.env['sale.order'].search([('id', '=', self.sale_order_id.id)])
        ReservedFund = self.env['reserved.fund']
        for order in sale_order_id:
            res_funds = ReservedFund.search([('order_id', '=', order.id)])
            # res_funds.unlink()
            res_funds.write({
                'active': False,
            })
            order.paid = True
            msg = "<b>Funds unreserved</b><ul>"
            msg += "<li>Reservation Reversed for %s <br/> for Order %s for an amount of <br/> %s %d by %s" % (
                order.partner_id.name, order.name, order.company_id.currency_id.symbol, order.order_total,
                order.user_id.name)
            msg += "</ul>"
            order.message_post(body=msg)

    @api.model
    def _get_default_team(self):
        return self.env['crm.team']._get_default_team_id()

    @api.model
    def create(self, vals):
        if self._context.get('invoice_type') == 'refund':
            credit_note_group_id = self.env.ref('inuka.credit_notes_group').id
            user_group_ids = self.env['res.users'].browse(self._uid).groups_id.ids
            if credit_note_group_id not in user_group_ids:
                raise UserError(_('Warning.\nUser must have rights for Credit Note!'))
        return super(AccountInvoice, self).create(vals)

    @api.multi
    def write(self, vals):
        if self._context.get('type') in ['in_refund', 'out_refund']:
            credit_note_group_id = self.env.ref('inuka.credit_notes_group').id
            user_group_ids = self.env['res.users'].browse(self._uid).groups_id.ids
            if credit_note_group_id not in user_group_ids:
                raise UserError(_('Warning.\nUser must have rights for Credit Note!'))
        return super(AccountInvoice, self).write(vals)

    @api.model
    def search(self, args, offset=False, limit=None, order=None, count=False):
        previous_date = fields.Datetime.to_string(date.today() + relativedelta(months=-3))  # Getting 3 month before date
        if not self.user_has_groups("account.group_account_user, account.group_account_manager"):
            args += [('create_date', '>=', previous_date)]
        return super(AccountInvoice, self).search(args=args, offset=offset, limit=limit, order=order, count=count)

    @api.one
    def _get_outstanding_info_JSON(self):
        self.outstanding_credits_debits_widget = json.dumps(False)
        if self.state == 'open':
            domain = [('account_id', '=', self.account_id.id), ('partner_id', '=', self.env['res.partner']._find_accounting_partner(self.partner_id).id), ('reconciled', '=', False), '|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0)]
            if self.type in ('out_invoice', 'in_refund'):
                domain.extend([('credit', '>', 0), ('debit', '=', 0)])
                type_payment = _('Outstanding credits')
            else:
                domain.extend([('credit', '=', 0), ('debit', '>', 0)])
                type_payment = _('Outstanding debits')
            info = {'title': '', 'outstanding': True, 'content': [], 'invoice_id': self.id}
            lines = self.env['account.move.line'].search(domain)
            currency_id = self.currency_id
            if len(lines) != 0:
                amount = 0.0
                for line in lines:
                    # get the outstanding residual value in invoice currency
                    if line.currency_id and line.currency_id == self.currency_id:
                        amount_to_show = abs(line.amount_residual_currency)
                    else:
                        amount_to_show = line.company_id.currency_id.with_context(date=line.date).compute(abs(line.amount_residual), self.currency_id)
                    if float_is_zero(amount_to_show, precision_rounding=self.currency_id.rounding):
                        continue
                    if amount >= self.residual:
                        break
                    info['content'].append({
                        'journal_name': line.ref or line.move_id.name,
                        'amount': amount_to_show,
                        'currency': currency_id.symbol,
                        'id': line.id,
                        'position': currency_id.position,
                        'digits': [69, self.currency_id.decimal_places],
                    })
                    amount += amount_to_show
                info['title'] = type_payment
                self.outstanding_credits_debits_widget = json.dumps(info)
                self.has_outstanding = True


    purchase_type = fields.Selection([
        ('it', 'IT'),
        ('​stationery', '​Stationery'),
        ('warehouse​', 'Warehouse​ supplies (stock)'),
        ('furniture', 'Furniture'),
        ('repairs', 'Repairs'),
        ('services​', 'Services​ (Training​ etc)'),
        ('rental​', 'Rental​ (Car​ park​ etc)'),
        ('stock', 'Stock'),
        ('marketing​', 'Marketing​ ​ Material')
        ], string='Purchase Type', default='it', readonly=True, states={'draft': [('readonly', False)]})
    total_pv = fields.Float(compute='_compute_tot_pv', store=True)
    payment_reference = fields.Char("Payment Reference", states={'draft': [('readonly', False)]})
    approved_for_payment = fields.Boolean("Approved for Payment", readonly=True, copy=False)
    sale_date = fields.Date('Sale Date', track_visibility='onchange')
    sale_order_id = fields.Many2one('sale.order', compute="_compute_sale_order", string="Sales Order")
    channel = fields.Selection([
        ('front', 'Front Office'),
        ('admin', 'Admin'),
        ('portal', 'Online Portal'),
        ('mobile', 'Mobile Application'),
    ], string="Channel")
    team_id = fields.Many2one('crm.team', string='Sales Team', default=_get_default_team, oldname='section_id')
    reason_id = fields.Many2one('account.invoice.refund.reason', string="Reason")
    invoice_printed = fields.Boolean(string="Invoice Printed?", copy=False, default=False)
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
    kit_order = fields.Boolean(compute="_compute_kit_order", string="Kit Order")

    def _compute_kit_order(self):
        category = self.env['product.category'].search([('name', '=', 'Kits')], limit=1)
        for invoice in self:
            for line in invoice.invoice_line_ids:
                if line.product_id.categ_id == category:
                    invoice.kit_order = True
                else:
                    invoice.kit_order = False

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False,
                        submenu=False):
        ctx = self.env.context.copy()
        ctx.update({'group_change_unit_prices': self.env.user.has_group('inuka.change_unit_prices')})
        res = super(AccountInvoice, self.with_context(ctx)).fields_view_get(
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

    @api.multi
    @api.onchange('reason_id')
    def onchange_reason_id(self):
        self.name = self.reason_id.name if self.reason_id else False

    @api.depends('invoice_line_ids', 'invoice_line_ids.pv')
    def _compute_tot_pv(self):
        for invoice in self:
            tot_pvs = 0.0
            for line in invoice.invoice_line_ids:
                tot_pvs += line.pv
            invoice.total_pv = tot_pvs

    def _compute_sale_order(self):
        SaleOrder = self.env['sale.order']
        for invoice in self:
            invoice.sale_order_id = SaleOrder.search([('name', '=', invoice.origin)], limit=1).id

    @api.onchange('purchase_id')
    def purchase_order_change(self):
        self.purchase_type = self.purchase_id.purchase_type
        self.payment_reference = self.purchase_id.payment_reference
        super(AccountInvoice, self).purchase_order_change()

    @api.multi
    def action_invoice_open(self):
        SaleOrder = self.env['sale.order']
        context = dict(self.env.context or {})
        for invoice in self:
            purchase_ids = invoice.invoice_line_ids.mapped('purchase_id')
            total = sum(purchase_ids.mapped('amount_total'))
            if purchase_ids and invoice.amount_total != total:
                context['active_id'] = invoice.id
                return {
                    'name': _('Warning'),
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'account.invoice.validate',
                    'type': 'ir.actions.act_window',
                    'context': context,
                    'target': 'new'
                }
#             if invoice.type == 'in_invoice' and not invoice.approved_for_payment:
#                 raise UserError(_('Vendor bill should be approved for payment before you Validate.'))
        return super(AccountInvoice, self).action_invoice_open()

    @api.multi
    def action_approve_bill(self):
        for invoice in self:
            if invoice.type == 'in_invoice':
                if not (self.user_has_groups('purchase.group_purchase_manager') or invoice.user_id.id == invoice.env._uid):
                    raise UserError(_('Only the PO Requestor or Purchase Managers can Approve for Payment.'))
                invoice.approved_for_payment = True
                invoice.action_invoice_open()
        return True

    @api.multi
    @api.returns('self')
    def refund(self, date_invoice=None, date=None, description=None, journal_id=None):
        res = super(AccountInvoice, self).refund(date_invoice=None, date=None, description=None, journal_id=None)
        if self._context.get('refund_invoice_id'):
            account_invoice_refund_id = self.env['account.invoice.refund'].browse(self._context.get('refund_invoice_id'))
            for each in res:
                each.update({'reason_id': account_invoice_refund_id.reason_id.id,
                             'sale_date': account_invoice_refund_id.date_invoice})
        return res

    @api.multi
    def _get_printed_report_name(self):
        res = super(AccountInvoice, self)._get_printed_report_name()
        if self.invoice_printed:
            return 'Copy - ' + res
        self.invoice_printed = True
        return res


class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"

    unit_pv = fields.Float("Unit PV")
    pv = fields.Float("PV's")
    price_unit_custom = fields.Float(string="Price Unit", related="price_unit")

    @api.onchange('product_id')
    def _onchange_product_id(self):
        super(AccountInvoiceLine, self)._onchange_product_id()
        self.pv = 0 if self.discount > 0 else self.product_id.pv * self.quantity
        self.unit_pv = 0 if self.discount > 0 else self.product_id.pv

    @api.onchange('quantity')
    def _onchange_quantity(self):
        self.pv = 0 if self.discount > 0 else self.product_id.pv * self.quantity

    def _set_additional_fields(self, invoice):
        self.pv = 0 if self.discount > 0 else self.product_id.pv * self.quantity
        self.unit_pv = 0 if self.discount > 0 else self.product_id.pv
        super(AccountInvoiceLine, self)._set_additional_fields(invoice)

    @api.onchange('discount')
    def _set_pv_zero(self):
        if self.discount > 0:
            self.pv = 0
            self.unit_pv = 0
        else:
            self.pv = self.product_id.pv * self.quantity
            self.unit_pv = self.product_id.pv


class AccountInvoiceReport(models.Model):
    _inherit = 'account.invoice.report'

    team_id = fields.Many2one('crm.team', string='Sales Team')


class account_invoice_refund_reason(models.Model):
    _name = 'account.invoice.refund.reason'

    name = fields.Char(string="Reason")
    active = fields.Boolean(string='Active', default=True)


class account_invoice_refund(models.TransientModel):
    _inherit = 'account.invoice.refund'

    reason_id = fields.Many2one('account.invoice.refund.reason', string="Reason")

    @api.multi
    @api.onchange('reason_id')
    def onchange_reason_id(self):
        self.description = self.reason_id.name if self.reason_id else False

    @api.multi
    def invoice_refund(self):
        data_refund = self.read(['filter_refund'])[0]['filter_refund']
        return self.with_context(refund_invoice_id=self.id).compute_refund(data_refund)

