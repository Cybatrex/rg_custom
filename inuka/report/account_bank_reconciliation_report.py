# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.tools.misc import formatLang


class master_account_bank_reconciliation_report(models.AbstractModel):
    _name = 'master.account.bank.reconciliation.report'
    _description = 'Master Bank Reconciliation Report'
    _inherit = "account.report"

    filter_date = {'date': '', 'filter': 'today'}

    #used to enumerate the 'layout' lines with a distinct ID
    line_number = 0

    def get_columns_name(self, options):
        return [
            {'name': ''},
            {'name': _("Date")},
            {'name': _("Reference")},
            {'name': _("Amount"), 'class': 'number'},
        ]

    def add_title_line(self, options, title, amount):
        self.line_number += 1
        return {
            'id': 'line_' + str(self.line_number),
            'name': title,
            'columns': [{'name': v} for v in [options['date']['date'], '', self.format_value(amount)]],
            'level': 0,
        }

    def add_subtitle_line(self, title, amount=None):
        self.line_number += 1
        return {
            'id': 'line_' + str(self.line_number),
            'name': title,
            'columns': [{'name': v} for v in ['', '', amount and self.format_value(amount) or '']],
            'level': 1,
        }

    def add_total_line(self, amount):
        self.line_number += 1
        return {
            'id': 'line_' + str(self.line_number),
            'name': '',
            'columns': [{'name': v} for v in ["", "", self.format_value(amount)]],
            'level': 2,
        }

    def add_bank_statement_line(self, line, amount):
        name = line.name
        return {
            'id': str(line.id),
            #'statement_id': line.statement_id.id,
            #'type': 'bank_statement_id',
            'caret_options': True,
            'name': len(name) >= 85 and name[0:80] + '...' or name,
            'columns': [{'name': v} for v in [line.date, line.ref, self.format_value(amount)]],
            'level': 1,
        }

    def print_pdf(self, options):
        options['active_id'] = self.env.context.get('active_id')
        return super(master_account_bank_reconciliation_report, self).print_pdf(options)

    def print_xlsx(self, options):
        options['active_id'] = self.env.context.get('active_id')
        return super(master_account_bank_reconciliation_report, self).print_xlsx(options)

    @api.model
    def get_lines(self, options, line_id=None):
        journal_id = self._context.get('active_id') or options.get('active_id')
        journal = self.env['account.journal'].browse(journal_id)
        lines = []
        #Start amount
        use_foreign_currency = bool(journal.currency_id)
        account_ids = list(set([journal.default_debit_account_id.id, journal.default_credit_account_id.id]))
        bank_statement_lines = self.env['account.bank.statement.line'].search([
                                                                        ('date', '<=', self.env.context['date_to']),
                                                                        ('company_id', 'in', self.env.context['company_ids'])])
        start_amount = sum([line.amount_currency if use_foreign_currency else line.amount for line in bank_statement_lines])
        lines.append(self.add_title_line(options, _("Total Transaction Amount"), start_amount))

        # Un-reconcilied bank statement lines
        unreconciled_statement_lines = self.env['account.bank.statement.line'].search([
                                                           ('statement_reconciled', '=', False),
                                                           ('date', '<=', self.env.context['date_to']),
                                                           ('company_id', 'in', self.env.context['company_ids'])])
        unrec_tot = 0
        if unreconciled_statement_lines:
            tmp_lines = []
            for line in unreconciled_statement_lines:
                self.line_number += 1
                tmp_lines.append({
                    'id': str(line.id),
                    'name': line.name,
                    'columns': [{'name': v} for v in [line.date, line.ref, self.format_value(line.amount)]],
                    'level': 1,
                })
                unrec_tot += line.amount_currency if use_foreign_currency else line.amount
            title=_("Unreconciled Transaction Lines")
            lines.append(self.add_subtitle_line(title))
            lines += tmp_lines
            lines.append(self.add_total_line(unrec_tot))

        # Un-reconcilied master bank statement lines
        unreconciled_master_statement_lines = self.env['master.account.bank.statement.line'].search([
                                                           ('statement_reconciled', '=', False),
                                                           ('date', '<=', self.env.context['date_to']),
                                                           ('company_id', 'in', self.env.context['company_ids'])])
        unrec_tot = 0
        if unreconciled_master_statement_lines:
            tmp_lines = []
            for line in unreconciled_master_statement_lines:
                self.line_number += 1
                tmp_lines.append({
                    'id': str(line.id),
                    #'move_id': line.move_id.id,
                    #'type': 'move_line_id',
                    #'action': line.get_model_id_and_name(),
                    'name': line.name,
                    'columns': [{'name': v} for v in [line.date, line.ref, self.format_value(line.amount)]],
                    'level': 1,
                })
                unrec_tot += line.amount_currency if use_foreign_currency else line.amount
            title=_("Unreconciled Statement Lines")
            lines.append(self.add_subtitle_line(title))
            lines += tmp_lines
            lines.append(self.add_total_line(unrec_tot))

        master_bank_statement_lines = self.env['master.account.bank.statement.line'].search([
                                                                        ('date', '<=', self.env.context['date_to']),
                                                                        ('company_id', 'in', self.env.context['company_ids'])])
        start_amount = sum([line.amount_currency if use_foreign_currency else line.amount for line in master_bank_statement_lines])
        lines.append(self.add_title_line(options, _("Total Statement Amount"), start_amount))
        return lines

    @api.model
    def get_report_name(self):
        journal_id = self._context.get('active_id')
        if journal_id:
            journal = self.env['account.journal'].browse(journal_id)
            return _("Master Bank Reconciliation") + ': ' + journal.name
        return _("Master Bank Reconciliation")
