# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import zipfile
import os
from io import BytesIO
from odoo import api, fields, models, _
from odoo.tools.osutil import tempdir


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    product_ids = fields.Many2many('product.product', 'helpdesk_ticket_product_rel', 'ticket_id', 'product_id',
                                   string="Products")
    mobile = fields.Char("Customer Mobile")
    sale_order_count = fields.Integer(compute="_compute_sale_order_count", string="Sale Orders")
    is_close = fields.Boolean(related="stage_id.is_close")
    sms_count = fields.Integer(compute="_compute_sms_count", string="SMS Count")
    fund_transfer_visible = fields.Boolean(string='Fund Transfer Visible', compute="_compute_fund_transfer_visible", store=True)

    @api.multi
    @api.depends('stage_id')
    def _compute_fund_transfer_visible(self):
        for each in self:
            if each.stage_id.name in ('New', 'In Progress'):
                each.fund_transfer_visible = True
            else:
                each.fund_transfer_visible = False

    @api.multi
    def fund_transfer(self):
        action = self.env.ref('inuka.action_fund_transfer_form_view').read()[0]
        action['context'] = {'default_partner_id': self.partner_id.id, 'from_partner': True}
        return action

    def _compute_sms_count(self):
        SmsMessage = self.env['sms.message']
        model_id = self.env['ir.model'].search([('model', '=', 'helpdesk.ticket')], limit=1).id
        for ticket in self:
            ticket.sms_count = SmsMessage.search_count([('model_id', '=', model_id), ('record_id', '=', ticket.id)])

    def _compute_sale_order_count(self):
        SaleOrder = self.env['sale.order']
        for ticket in self:
            ticket.sale_order_count = SaleOrder.search_count([('ticket_id', '=', ticket.id)])

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        super(HelpdeskTicket, self)._onchange_partner_id()
        if self.partner_id:
            self.mobile = self.partner_id.mobile

    # @api.model
    # def search(self, args, offset=0, limit=None, order=None, count=False):
    #     if args is None:
    #         args = []
    #     teams = self.env['helpdesk.team'].search([('member_ids', 'in', [self.env.uid])])
    #     args += [('team_id', 'in', teams.ids)]
    #     return super(HelpdeskTicket, self).search(args, offset, limit, order, count=count)

    @api.multi
    def create_sale_order(self):
        self.ensure_one()
        saleorder = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'ticket_id': self.id,
        })
        stage = self.env['helpdesk.stage'].search([('name', '=', 'Solved')], limit=1)
        self.write({'stage_id': stage.id})
        msg = "This Sales Order has been created from Ticket {%s}: <a href=# data-oe-model=helpdesk.ticket data-oe-id=%d>{%s}</a>" % (
            self.id, self.id, self.name)
        saleorder.message_post(body=msg)
        view_id = self.env.ref('sale.view_order_form').id
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sale.order',
            'views': [(view_id, 'form')],
            'view_id': view_id,
            'res_id': saleorder.id,
        }

    @api.multi
    def view_sms_message(self):
        self.ensure_one()
        model_id = self.env['ir.model'].search([('model', '=', 'helpdesk.ticket')], limit=1).id
        messages = self.env['sms.message'].search([('model_id', '=', model_id), ('record_id', '=', self.id)])

        return {
            'name': _('Messages'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'sms.message',
            'context': self.env.context,
            'domain': [('id', 'in', messages.ids)],
        }

    @api.multi
    def import_bank_statement(self):
        ResPartnerBank = self.env['res.partner.bank']
        stage = self.env['helpdesk.stage'].search([('name', '=', 'Solved')], limit=1)
        for ticket in self:
            attachments = self.env['ir.attachment'].search(
                [('res_id', '=', ticket.id), ('res_model', '=', 'helpdesk.ticket')])
            if not attachments:
                continue

            acc_number = ticket.name.split("[")[1][:-1]
            bank_account_id = ResPartnerBank.search([('acc_number', 'in', (acc_number, '00000' + acc_number))],
                                                    limit=1).id
            journal_id = self.env['account.journal'].search([('bank_account_id', '=', bank_account_id)], limit=1).id
            for attachment in attachments:
                fp = BytesIO()
                fp.write(base64.b64decode(attachment.datas))
                if not zipfile.is_zipfile(fp):
                    continue
                if zipfile.is_zipfile(fp):
                    with zipfile.ZipFile(fp, "r") as z:
                        with tempdir() as module_dir:
                            import odoo.modules.module as module
                            try:
                                module.ad_paths.append(module_dir)
                                z.extractall(module_dir)
                                for d in os.listdir(module_dir):
                                    extract_file = z.open(d)
                                    new_rec = self.env['account.bank.statement.import'].with_context(
                                        journal_id=journal_id).create(
                                        {'data_file': base64.b64encode(extract_file.read()), 'filename': 'test'})
                                    new_rec.with_context(ticket=ticket).import_file()
                                    ticket.write({'stage_id': stage.id})
                            except Exception as e:
                                ticket.message_post(body=str(e))
                            finally:
                                module.ad_paths.remove(module_dir)

    @api.multi
    def import_master_bank_statement(self):
        ResPartnerBank = self.env['res.partner.bank']
        stage = self.env['helpdesk.stage'].search([('name', '=', 'Solved')], limit=1)
        for ticket in self:
            attachments = self.env['ir.attachment'].search(
                [('res_id', '=', ticket.id), ('res_model', '=', 'helpdesk.ticket')])
            if not attachments:
                continue

            acc_number = ticket.name.split("[")[1][:-1]
            bank_account_id = ResPartnerBank.search([('acc_number', 'in', (acc_number, '00000' + acc_number))],
                                                    limit=1).id
            journal_id = self.env['account.journal'].search([('bank_account_id', '=', bank_account_id)], limit=1).id
            for attachment in attachments:
                fp = BytesIO()
                fp.write(base64.b64decode(attachment.datas))
                if not zipfile.is_zipfile(fp):
                    continue
                if zipfile.is_zipfile(fp):
                    with zipfile.ZipFile(fp, "r") as z:
                        with tempdir() as module_dir:
                            import odoo.modules.module as module
                            try:
                                module.ad_paths.append(module_dir)
                                z.extractall(module_dir)
                                for d in os.listdir(module_dir):
                                    extract_file = z.open(d)
                                    new_rec = self.env['master.account.bank.statement.import'].with_context(
                                        journal_id=journal_id).create(
                                        {'data_file': base64.b64encode(extract_file.read()), 'filename': 'test'})
                                    new_rec.with_context(ticket=ticket).import_file()
                                    ticket.write({'stage_id': stage.id})
                            except Exception as e:
                                ticket.message_post(body=str(e))
                            finally:
                                module.ad_paths.remove(module_dir)

    @api.multi
    def view_sale_orders(self):
        self.ensure_one()
        orders = self.env['sale.order'].search([('ticket_id', '=', self.id)])
        action = self.env.ref('sale.action_orders').read()[0]
        action['domain'] = [('id', 'in', orders.ids)]
        return action

    def sms_action(self):
        self.ensure_one()
        if int(str(self.mobile)[:2]) == 27:
            default_mobile = self.env['sms.number'].search([('name', '=', 'INUKA Local')])
        else:
            default_mobile = self.env['sms.number'].search([('name', '=', 'INUKA International')])
        
        return {
            'name': 'SMS Compose',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sms.compose',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'context': {'default_from_mobile_id': default_mobile.id, 'default_to_number': self.mobile,
                        'default_record_id': self.id, 'default_model': 'helpdesk.ticket'}
        }


class SaleOrder(models.Model):
    _inherit = "sale.order"

    ticket_id = fields.Many2one("helpdesk.ticket", string="Tickets")


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model
    def create(self, vals):
        res = super(IrAttachment, self).create(vals)
        if res.res_model == 'helpdesk.ticket' and 'FNB RSA OFX' in res.res_name and 'Hourly' in res.res_name:
            self.env['helpdesk.ticket'].browse(res.res_id).import_bank_statement()
        elif res.res_model == 'helpdesk.ticket' and 'FNB RSA OFX' in res.res_name and 'Hourly' not in res.res_name:
            self.env['helpdesk.ticket'].browse(res.res_id).import_master_bank_statement()
        return res
