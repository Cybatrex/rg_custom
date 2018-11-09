# -*- coding: utf-8 -*-
from odoo import api, models, fields
from odoo.addons.payment_paygate.controllers.main import payGateController

from datetime import datetime
from hashlib import md5
import logging


_logger = logging.getLogger(__name__)

class payGate(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[('payget', 'Paygate')])
    paygate_id = fields.Char('Paygate ID', help="Paygate id provided by payget provider")

    @api.model
    def _get_paygate_urls(self, environment):
        return {
            'paygate_form_url': ' https://secure.paygate.co.za/payweb3/initiate.trans'
            }

    @api.multi
    def paygate_get_form_action_url(self):
        return self._get_paygate_urls(self.environment)['paygate_form_url']

    @api.multi
    def paygate_form_generate_values(self, values):
        self.ensure_one()
        values['PAYGATE_ID'] = self.paygate_id or '10011072130'
        values['REFERENCE'] = values['reference']
        values['AMOUNT'] = values['amount']
        values['CURRENCY'] = 'ZAR'
        values['TRANSACTION_DATE'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        values['LOCALE'] = 'en'
        values['COUNTRY'] = 'ZAF'
        values['EMAIL'] = values['partner_email']
        values['RETURN_URL'] = payGateController._return_url
        values['NOTIFY_URL'] = payGateController._notify_url
        values['CHECKSUM'] = self.calculate_md5(values)

    @api.model
    def calculate_md5(self, data):
        checksum = ''
        key = 'secret'  # Make sure
        for k, v in data.items():
            checksum = '%s%s' % (checksum, v)
        checksum = '%s%s' % (checksum, key)  # add key to checksum value
        md5_hash = md5(checksum.encode('utf-8')).hexdigest()
        return md5_hash

    @api.model
    def validate_checksum(self, data):
        hash_ = data.pop('CHECKSUM')
        new_hash = self.calculate_md5(data)
        return hash_ == new_hash, new_hash
