# -*- coding: utf-8 -*-

from odoo import api, models


class AccountInvoiceValidate(models.TransientModel):
    _name = "account.invoice.validate"

    @api.multi
    def invoice_confirm(self):
        self.ensure_one()
        context = dict(self.env.context or {})
        active_id = context.get('active_id')
        record = self.env['account.invoice'].browse(active_id)

        record.action_date_assign()
        record.action_move_create()
        record.invoice_validate()

        return {'type': 'ir.actions.act_window_close'}
