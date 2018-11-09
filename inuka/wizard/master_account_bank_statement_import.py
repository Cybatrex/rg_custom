# -*- coding: utf-8 -*-

import base64
import datetime
import io
import logging
import hashlib
import re
from xml.etree import ElementTree

try:
    from ofxparse import OfxParser
    from ofxparse.ofxparse import OfxParserException
    OfxParserClass = OfxParser
except ImportError:
    logging.getLogger(__name__).warning("The ofxparse python library is not installed, ofx import will not work.")
    OfxParser = OfxParserException = None
    OfxParserClass = object

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.base.res.res_bank import sanitize_account_number
from odoo.addons.account_bank_statement_import_ofx.wizard.account_bank_statement_import_ofx import *

import logging
_logger = logging.getLogger(__name__)


class MasterAccountBankStatementLine(models.Model):
    _inherit = "master.account.bank.statement.line"

    # Ensure transactions can be imported only once (if the import format provides unique transaction ids)
    unique_import_id = fields.Char(string='Import ID', readonly=True, copy=False)

#     _sql_constraints = [
#         ('unique_import_id', 'unique (unique_import_id)', 'A bank account transactions can be imported only once !')
#     ]


class MasterAccountBankStatementImport(models.TransientModel):
    _name = 'master.account.bank.statement.import'
    _description = 'Import Master Bank Statement'

    data_file = fields.Binary(string='Bank Statement File', required=True, help='Get you bank statements in electronic format from your bank and select them here.')
    filename = fields.Char()

    @api.multi
    def import_file(self):
        """ Process the file chosen in the wizard, create bank statement(s) and go to reconciliation. """
        self.ensure_one()
        # Let the appropriate implementation module parse the file and return the required data
        # The active_id is passed in context in case an implementation module requires information about the wizard state (see QIF)
        currency_code, account_number, stmts_vals = self.with_context(active_id=self.ids[0])._parse_file(base64.b64decode(self.data_file))
        # Check raw data
        self._check_parsed_data(stmts_vals)
        # Try to find the currency and journal in odoo
        currency, journal = self._find_additional_data(currency_code, account_number)
        # If no journal found, ask the user about creating one
        if not journal:
            # The active_id is passed in context so the wizard can call import_file again once the journal is created
            return self.with_context(active_id=self.ids[0])._journal_creation_wizard(currency, account_number)
        if not journal.default_debit_account_id or not journal.default_credit_account_id:
            raise UserError(_('You have to set a Default Debit Account and a Default Credit Account for the journal: %s') % (journal.name,))
        # Prepare statement data to be used for bank statements creation
        stmts_vals = self._complete_stmts_vals(stmts_vals, journal, account_number)
        # Create the bank statements
        statement_ids, notifications = self._create_bank_statements(stmts_vals)
        self.env['master.account.bank.statement'].browse(statement_ids).reconcile_master_statement()
        # Now that the import worked out, set it as the bank_statements_source of the journal
        journal.bank_statements_source = 'file_import'
        # Finally dispatch to reconciliation interface
        action = self.env.ref('account.action_bank_reconcile_bank_statements')
        return True
#         return {
#             'name': action.name,
#             'tag': action.tag,
#             'context': {
#                 'statement_ids': statement_ids,
#                 'notifications': notifications
#             },
#             'type': 'ir.actions.client',
#         }

    def _journal_creation_wizard(self, currency, account_number):
        """ Calls a wizard that allows the user to carry on with journal creation """
        return {
            'name': _('Journal Creation'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement.import.journal.creation',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'statement_import_transient_id': self.env.context['active_id'],
                'default_bank_acc_number': account_number,
                'default_name': _('Bank') + ' ' + account_number,
                'default_currency_id': currency and currency.id or False,
                'default_type': 'bank',
            }
        }

    def _check_ofx(self, data_file):
        if data_file.startswith(b"OFXHEADER"):
            #v1 OFX
            return True
        try:
            #v2 OFX
            return b"<ofx>" in data_file.lower()
        except ElementTree.ParseError:
            return False

    def _get_branch(self, memo):
        if memo[21:21] == "":
           return memo[:21].strip()
        else:
            bank_list = ["ABSA BANK", "CAPITEC", "SPEEDPOINT"]
            for bank in bank_list:
                if memo.find(bank) > 0:
                    return bank
        if len(memo) < 21:
            return memo.strip()
        else:
            return memo[:21].strip()

    def _get_label(self, memo, bank):
        result = memo
        if memo.strip() != bank.strip():
            if bank:
                result = memo.replace(bank, "").strip()
        return result

    def _get_partner(self, label):
        Partner = self.env['res.partner']
        search_string = label and label.split()[-1] or ''
        if len(search_string) == 6:
            partner = Partner.search([('ref', '=', search_string)], limit=1).id
        else:
            search_string = search_string.strip()
            if search_string.startswith("06"):
                search_string = search_string.replace("06", "276", 1)
            elif search_string.startswith("07"):
                search_string = search_string.replace("07", "277", 1)
            elif search_string.startswith("08"):
                search_string = search_string.replace("08", "278", 1)
            partner = Partner.search([('mobile', '=', search_string)], limit=1).id
        return partner

    def _parse_file(self, data_file):
        journal_id = self.env.context.get('journal_id', [])
        bank_name = self.env['account.journal'].browse(journal_id).bank_id.name or ""
        if not self._check_ofx(data_file):
            return super(MasterAccountBankStatementImport, self)._parse_file(data_file)
        if OfxParser is None:
            raise UserError(_("The library 'ofxparse' is missing, OFX import cannot proceed."))

        ofx = PatchedOfxParser.parse(io.BytesIO(data_file))
        vals_bank_statement = []
        account_lst = set()
        currency_lst = set()
        for account in ofx.accounts:
            account_lst.add(account.number)
            currency_lst.add(account.statement.currency)
            transactions = []
            total_amt = 0.00
            for transaction in account.statement.transactions:
                # Since ofxparse doesn't provide account numbers, we'll have to find res.partner and res.partner.bank here
                # (normal behaviour is to provide 'account_number', which the generic module uses to find partner/bank)
                bank_account_id = partner_id = False
                partner_bank = self.env['res.partner.bank'].search([('partner_id.name', '=', transaction.payee)], limit=1)
                if partner_bank:
                    bank_account_id = partner_bank.id
                    partner_id = partner_bank.partner_id.id
                reference = str(transaction.date) + str(transaction.amount) + transaction.memo
                label = self._get_label(transaction.memo, bank_name)
                vals_line = {
                    'date': transaction.date,
                    'name': label,
                    'ref': hashlib.md5(reference.encode('utf-8')).hexdigest(),
#                     'fitid': transaction.id,
                    'branch': self._get_branch(transaction.memo),
                    'amount': transaction.amount,
                    'unique_import_id': '',
                    'bank_account_id': bank_account_id,
                    'partner_id': self._get_partner(label),
#                     'sequence': len(transactions) + 1,
                }
                total_amt += float(transaction.amount)
                transactions.append(vals_line)

            vals_bank_statement.append({
                'transactions': transactions,
                # WARNING: the provided ledger balance is not necessarily the ending balance of the statement
                # see https://github.com/odoo/odoo/issues/3003
                'balance_start': float(account.statement.balance) - total_amt,
                'balance_end_real': account.statement.balance,
                'name': ofx.signon.dtserver,
            })

        if account_lst and len(account_lst) == 1:
            account_lst = account_lst.pop()
            currency_lst = currency_lst.pop()
        else:
            account_lst = None
            currency_lst = None

        return currency_lst, account_lst, vals_bank_statement

    def _check_parsed_data(self, stmts_vals):
        """ Basic and structural verifications """
        if len(stmts_vals) == 0:
            raise UserError(_('This file doesn\'t contain any statement.'))

        no_st_line = True
        for vals in stmts_vals:
            if vals['transactions'] and len(vals['transactions']) > 0:
                no_st_line = False
                break
        if no_st_line:
            raise UserError(_('This file doesn\'t contain any transaction.'))

    def _check_journal_bank_account(self, journal, account_number):
        return journal.bank_account_id.sanitized_acc_number == account_number

    def _find_additional_data(self, currency_code, account_number):
        """ Look for a res.currency and account.journal using values extracted from the
            statement and make sure it's consistent.
        """
        company_currency = self.env.user.company_id.currency_id
        journal_obj = self.env['account.journal']
        currency = None
        sanitized_account_number = sanitize_account_number(account_number)

        if currency_code:
            currency = self.env['res.currency'].search([('name', '=ilike', currency_code)], limit=1)
            if not currency:
                raise UserError(_("No currency found matching '%s'.") % currency_code)
            if currency == company_currency:
                currency = False

        journal = journal_obj.browse(self.env.context.get('journal_id', []))
        if account_number:
            # No bank account on the journal : create one from the account number of the statement
            if journal and not journal.bank_account_id:
                journal.set_bank_account(account_number)
            # No journal passed to the wizard : try to find one using the account number of the statement
            elif not journal:
                journal = journal_obj.search([('bank_account_id.sanitized_acc_number', '=', sanitized_account_number)])
            # Already a bank account on the journal : check it's the same as on the statement
            else:
                if not self._check_journal_bank_account(journal, sanitized_account_number):
                    raise UserError(_('The account of this statement (%s) is not the same as the journal (%s).') % (account_number, journal.bank_account_id.acc_number))

        # If importing into an existing journal, its currency must be the same as the bank statement
        if journal:
            journal_currency = journal.currency_id
            if currency is None:
                currency = journal_currency
            if currency and currency != journal_currency:
                statement_cur_code = not currency and company_currency.name or currency.name
                journal_cur_code = not journal_currency and company_currency.name or journal_currency.name
                raise UserError(_('The currency of the bank statement (%s) is not the same as the currency of the journal (%s) !') % (statement_cur_code, journal_cur_code))

        # If we couldn't find / can't create a journal, everything is lost
        if not journal and not account_number:
            raise UserError(_('Cannot find in which journal import this statement. Please manually select a journal.'))

        return currency, journal

    def _complete_stmts_vals(self, stmts_vals, journal, account_number):
        for st_vals in stmts_vals:
            st_vals['journal_id'] = journal.id
            if not st_vals.get('reference'):
                st_vals['reference'] = self.filename
            if st_vals.get('number'):
                #build the full name like BNK/2016/00135 by just giving the number '135'
                st_vals['name'] = journal.sequence_id.with_context(ir_sequence_date=st_vals.get('date')).get_next_char(st_vals['number'])
                del(st_vals['number'])
            for line_vals in st_vals['transactions']:
                unique_import_id = line_vals.get('unique_import_id')
                sanitized_account_number = sanitize_account_number(account_number)
                line_vals['unique_import_id'] = (sanitized_account_number and sanitized_account_number + '-' or '') + str(journal.id) + '-' + line_vals.get('ref')
            
            
#                 if not line_vals.get('bank_account_id'):
#                     # Find the partner and his bank account or create the bank account. The partner selected during the
#                     # reconciliation process will be linked to the bank when the statement is closed.
#                     partner_id = False
#                     bank_account_id = False
#                     identifying_string = line_vals.get('account_number')
#                     if identifying_string:
#                         partner_bank = self.env['res.partner.bank'].search([('acc_number', '=', identifying_string)], limit=1)
#                         if partner_bank:
#                             bank_account_id = partner_bank.id
#                             partner_id = partner_bank.partner_id.id
#                         else:
#                             bank_account_id = self.env['res.partner.bank'].create({'acc_number': line_vals['account_number']}).id
#                     line_vals['partner_id'] = partner_id
#                     line_vals['bank_account_id'] = bank_account_id

        return stmts_vals

    def _create_bank_statements(self, stmts_vals):
        """ Create new bank statements from imported values, filtering out already imported transactions, and returns data used by the reconciliation widget """
        BankStatement = self.env['master.account.bank.statement']
        BankStatementLine = self.env['master.account.bank.statement.line']

        # Filter out already imported transactions and create statements
        statement_ids = []
        ignored_statement_lines_import_ids = []
        for st_vals in stmts_vals:
            filtered_st_lines = []
            filtered_st_lines_new = []
            for line_vals in st_vals['transactions']:
                flag = False
                for each in BankStatementLine.sudo().search([]):
                    if each.unique_import_id == line_vals['unique_import_id']:
                        flag = True
                if not flag:
                    filtered_st_lines.append(line_vals)
                else:
                    ignored_statement_lines_import_ids.append(line_vals['unique_import_id'])
                    if 'balance_start' in st_vals:
                        st_vals['balance_start'] += float(line_vals['amount'])
#                 if ('unique_import_id' not in line_vals \
#                    or not line_vals['unique_import_id'] \
#                    or 'ref' not in line_vals \
#                    or not line_vals['ref']
#                    or not bool(BankStatementLine.sudo().search([('unique_import_id', '=', line_vals['unique_import_id'])], limit=1))) \
#                    and not bool(BankStatementLine.sudo().search([('ref', '=', line_vals['ref'])], limit=1)):
#                         if line_vals not in filtered_st_lines:
#                             filtered_st_lines.append(line_vals)
#                     
#                 else:
#                     ignored_statement_lines_import_ids.append(line_vals['unique_import_id'])
#                     if 'balance_start' in st_vals:
#                         st_vals['balance_start'] += float(line_vals['amount'])
            if len(filtered_st_lines) > 0:
                # Remove values that won't be used to create records
                st_vals.pop('transactions', None)
                count = 0
                for line_vals in filtered_st_lines:
                    count += 1
                    line_vals.update({'sequence': count})
                    line_vals.pop('account_number', None)
                # Create the satement
                st_vals['line_ids'] = [[0, False, line] for line in filtered_st_lines]
                statement_ids.append(BankStatement.create(st_vals).id)
        if len(statement_ids) == 0:
            context = dict(self.env.context or {})
            ticket = context.get('ticket')
            if ticket:
                ticket.write({'stage_id': self.env.ref('inuka.stage_already_imported').id})
            raise UserError(_('You have already imported that file.'))

        # Prepare import feedback
        notifications = []
        num_ignored = len(ignored_statement_lines_import_ids)
        if num_ignored > 0:
            notifications += [{
                'type': 'warning',
                'message': _("%d transactions had already been imported and were ignored.") % num_ignored if num_ignored > 1 else _("1 transaction had already been imported and was ignored."),
                'details': {
                    'name': _('Already imported items'),
                    'model': 'account.bank.statement.line',
                    'ids': BankStatementLine.search([('unique_import_id', 'in', ignored_statement_lines_import_ids)]).ids
                }
            }]
        return statement_ids, notifications
