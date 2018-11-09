# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import copy
from odoo import models, fields, api, _
from odoo.tools.safe_eval import safe_eval
from odoo.tools.misc import formatLang
from odoo.tools import float_is_zero, ustr
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
from odoo.osv import expression


class ReportAccountFinancialReport(models.Model):
    _inherit = "account.financial.html.report"
    _description = "Account Report"

    accunt_tags = fields.Boolean('Allow Account Tags filter', help='display the account tags filter')

    @api.model
    def get_options(self, previous_options=None):
        if self.accunt_tags:
            self.filter_account_tag = self.env.user.id in self.env.ref('analytic.group_analytic_accounting').users.ids and True or None
        return super(ReportAccountFinancialReport, self).get_options(previous_options)


class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    filter_account_tag = None
