# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class fund_transfer_successful(models.TransientModel):
    _name = "fund.transfer.successful"

    @api.multi
    def transfer_fund_succesfull(self):
        return True


class fund_transfer(models.Model):
    _name = "fund.transfer"

    partner_id = fields.Many2one('res.partner', string="From")
    balance_available = fields.Float(string="Funds Available", compute="_compute_balance_available", store=True)
    transfer_to_ids = fields.One2many('fund.transfer.line', 'transfer_id', string="Transfer Funds To")
    move_id = fields.Many2one('account.move', string="Journal Entry")
    amount_to_transfer = fields.Float(string='Transferred Amount', compute="_compute_amount_to_transfer", store=True)
    state = fields.Selection([('draft', 'Draft'), ('post', 'Post')], default="draft")
    ticket_id = fields.Many2one('helpdesk.ticket', string="Ticket")

    @api.multi
    @api.depends('partner_id')
    def _compute_balance_available(self):
        for each in self:
            reserved_fund = self.env['reserved.fund'].search([('customer_id', '=', each.partner_id.id)], limit = 1)
            each.balance_available = (each.partner_id.debit - each.partner_id.credit) - reserved_fund.amount

    @api.multi
    @api.depends('transfer_to_ids')
    def _compute_amount_to_transfer(self):
        for each in self:
            each.amount_to_transfer = sum(each.transfer_to_ids.mapped('amount'))

    @api.multi
    def transfer_fund(self):
        for each in self:
            amount_to_transfer = sum(each.transfer_to_ids.mapped('amount'))
            if amount_to_transfer > each.balance_available:
                raise ValidationError(_('Warning!\nTotal amount to be transferred is more than the current balance.'))
        move_line = []
        move_line.append((0, 0, {'account_id': self.partner_id.property_account_receivable_id.id,
                                 'partner_id': self.partner_id.id,
                                 'name': self.partner_id.name + 'Funds Transfer ' + str(amount_to_transfer),
                                 'debit': amount_to_transfer,
                                 'credit': 0
                                 }))
        
        for each in self.transfer_to_ids:
            move_line.append((0, 0, {
                                     'account_id': each.partner_to_id.property_account_receivable_id.id,
                                     'partner_id': each.partner_to_id.id,
                                     'name': 'Funds Transfer from ' + self.partner_id.name + ' for ' + str(each.amount),
                                     'debit': 0,
                                     'credit': each.amount
                                     }))
        journal_id = self.env['account.journal'].sudo().search([('name', '=', 'Member Funds Transfer'), ('type', '=', 'general')], limit=1, order="id desc")
        if not journal_id:
            raise ValidationError(_("Warning!\nNo such Journal found for 'Member Funds Transfer'."))
        move_id = self.env['account.move'].create({
                                                 'journal_id': journal_id.id,
                                                 'ref': self.partner_id.name + ' Funds Transfer ' + str(amount_to_transfer),
                                                 'line_ids': move_line,
                                                  })
        move_id.post()
        if move_id:
            self.move_id = move_id
            self.state = 'post'
        transferred_to = ' ,'.join(str(e) for e in [x.partner_to_id.name for x in self.transfer_to_ids]) + '.'
        body = """
                <p>_____________________________</p>
                <p>Funds Transferred.</p>
                <ul>
                <li><b>Total Amount Transferred </b>: <span>%s.</span></li>
                <li><b>Transferred To </b>: <span>%s</span></li>
                </ul>
                <p>_____________________________</p>
               """%(str(amount_to_transfer), transferred_to)
        msg_id = self.env['mail.message'].create({'subject': 'Funds Transferred',
                                                  'body': body,
                                                  'model': self._context.get('active_model',False),
                                                  'res_id': self._context.get('active_id', False),
                                                  'message_type': 'notification',
                                                  })
        if self._context.get('active_model') == 'helpdesk.ticket' and self._context.get('active_id'):
            self.ticket_id = self._context.get('active_id')
        action = self.env.ref('inuka.action_fund_transfer_successful_form_view').read()[0]
        return action

    @api.multi
    def action_move_journal_line_custom(self):
        return {
                'type': 'ir.actions.act_window',
                'name': _('Journal Entry'),
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': self.move_id.id,
                'target': 'current',
                }

    @api.multi
    def action_ticket_form_custom(self):
        return {
                'type': 'ir.actions.act_window',
                'name': _('Ticket'),
                'res_model': 'helpdesk.ticket',
                'view_mode': 'form',
                'res_id': self.ticket_id.id,
                'target': 'current',
                }

    @api.multi
    def unlink(self):
        raise ValidationError(_("Warning!  \nYou cannot delete a Posted Funds Transfer."))


class fund_transfer_line(models.Model):
    _name = "fund.transfer.line"
    
    transfer_id = fields.Many2one('fund.transfer', string="TransferID")
    partner_to_id = fields.Many2one('res.partner', string="To")
    amount = fields.Float(string="Amount")