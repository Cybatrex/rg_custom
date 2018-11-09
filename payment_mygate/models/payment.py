# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from werkzeug import urls

from odoo import api, fields, models, _
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.tools.float_utils import float_compare

import logging

_logger = logging.getLogger(__name__)


class PaymentAcquirerMygate(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[('mygate', 'mygate')])
    mygate_merchant_id = fields.Char(string='Merchant Key', required_if_provider='mygate', groups='base.group_user')
    mygate_application_id = fields.Char(string='Merchant Application', required_if_provider='mygate', groups='base.group_user')

    def _get_mygate_urls(self, environment):
        """ mygate URLs"""
        if environment == 'prod':
            return {'mygate_form_url': 'https://virtual.mygateglobal.com/PaymentPage.cfm'}
        else:
            return {'mygate_form_url': 'https://virtual.mygateglobal.com/PaymentPage.cfm'}

    @api.multi
    def mygate_form_generate_values(self, values):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        mygate_values = dict(values,
                            mode=0 if self.environment == 'test' else 1,
                            merchantID=self.mygate_merchant_id,
                            applicationID=self.mygate_application_id,
                            merchantReference=values['reference'],
                            amount=values['amount'],
                            txtCurrencyCode=values['currency'] and values['currency'].name or '',
                            redirectSuccessfulURL=urls.url_join(base_url, '/payment/mygate/return'),
                            redirectFailedURL=urls.url_join(base_url, '/payment/mygate/error'),
                            recipient=values.get('partner_name'),
                            shippingAddress1=values.get('partner_address'),
                            shippingAddress2=values.get('partner_zip'),
                            shippingAddress3=values.get('partner_city'),
                            shippingAddress4=values.get('partner_state').name,
                            shippingAddress5=values.get('partner_country').name,
                            email=values.get('partner_email'),
                            phone=values.get('partner_phone'))
        return mygate_values

    @api.multi
    def mygate_get_form_action_url(self):
        self.ensure_one()
        return self._get_mygate_urls(self.environment)['mygate_form_url']


class PaymentTransactionmygate(models.Model):
    _inherit = 'payment.transaction'

    @api.model
    def _mygate_form_get_tx_from_data(self, data):
        """ Given a data dict coming from mygate, verify it and find the related
        transaction record. """
        reference = data.get('_MERCHANTREFERENCE')
        pay_id = data.get('_TRANSACTIONINDEX')
        shasign = data.get('_PANHASHED')
        if not reference or not pay_id or not shasign:
            _logger.warning(_('mygate: received data with missing reference (%s) or pay_id (%s) or shashign (%s)') % (reference, pay_id, shasign))

        transaction = self.search([('reference', '=', reference)])

        if not transaction:
            _logger.warning(_('mygate: received data for reference %s; no order found') % (reference))
        elif len(transaction) > 1:
            _logger.warning(_('mygate: received data for reference %s; multiple orders found') % (reference))
        return transaction

    @api.multi
    def _mygate_form_get_invalid_parameters(self, data):
        invalid_parameters = []

        if self.acquirer_reference and data.get('_TRANSACTIONINDEX') != self.acquirer_reference:
            invalid_parameters.append(
                ('Transaction Id', data.get('_TRANSACTIONINDEX'), self.acquirer_reference))
        #check what is buyed
        if float_compare(float(data.get('_AMOUNT', '0.0')), self.amount, 2) != 0:
            invalid_parameters.append(
                ('Amount', data.get('_AMOUNT'), '%.2f' % self.amount))

        return invalid_parameters

    @api.multi
    def _mygate_form_validate(self, data):
        status = data.get('_RESULT')
        transaction_status = {
            '0': {
                'state': 'done',
                'acquirer_reference': data.get('_TRANSACTIONINDEX'),
                'date_validate': fields.Datetime.now(),
            },
            '-1': {
                'state': 'error',
                'state_message': data.get('_ERROR_MESSAGE') or _('mygate: feedback error'),
                'acquirer_reference': data.get('_TRANSACTIONINDEX'),
                'date_validate': fields.Datetime.now(),
            }
        }
        vals = transaction_status.get(status, False)
        if not vals:
            vals = transaction_status['error']
            _logger.info(vals['state_message'])
        return self.write(vals)
