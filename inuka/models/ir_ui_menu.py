# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        menus = super(IrUiMenu, self).search(args, offset=0, limit=None, order=order, count=False)
        if self.env.user.has_group('inuka.group_cash_specialist') and not self.env.user.has_group("account.group_account_user") and not self.env.user.has_group("account.group_account_manager"):
            menus = menus - (self.env.ref('account.menu_finance_payables') + self.env.ref('account.menu_finance_entries') +
                self.env.ref('account.menu_finance_reports') + self.env.ref('account.menu_finance_configuration') +
                self.env.ref('account.menu_board_journal_1') + self.env.ref('account.menu_finance_receivables_follow_up'))
        return len(menus) if count else menus
