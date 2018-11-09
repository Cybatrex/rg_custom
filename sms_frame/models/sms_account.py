# -*- coding: utf-8 -*-
from openerp import api, fields, models

import urllib.request
import urllib.parse

import logging
_logger = logging.getLogger(__name__)

class SmsAccount(models.Model):
    _name = "sms.account"

    name = fields.Char(string='Account Name', required=True)
    account_gateway_id = fields.Many2one('sms.gateway', string="Account Gateway", required=True)
    gateway_model = fields.Char(string="Gateway Model", related="account_gateway_id.gateway_model_name")

    def send_message(self, from_number, to_number, sms_content, my_model_name='', my_record_id=0, media=None, queued_sms_message=None):
        _logger.info('clicKatell send message here 0000 ' + str(sms_content) )
        url = "https://api.clickatell.com/http/sendmsg"
        d = { "user": "inukaclick", "password": "click2inuka@2015", "from" : "27731332165" , "api_id": "3647950", "to": to_number, "text": sms_content }
        data = urllib.parse.urlencode(d).encode("utf-8")
        req = urllib.request.Request(url)
        rl = []
        with urllib.request.urlopen(url,data=data) as f:
            r = {}
            resp = f.read().decode('utf-8')
            print(resp)
            _logger.info('clicKatell send message here <<<>>>   ' + str(resp) )
            if resp[:2] == 'ID':
                r['apiMessageId'] = resp[3:].strip()
                r['id'] = resp[3:].strip()
            r['to'] = to_number
            r['accepted'] = ""
            if resp[:3] == 'ERR':
                r['errorCode'] = (resp[4:].strip())[:3]
                r['error'] = resp[4:].strip()
            else:
                r['errorCode'] = False
                r['error'] = False
            rl.append(r)
        """Send a message from this account"""
        #return self.env[self.gateway_model].send_message(self.id, from_number, to_number, sms_content, my_model_name, my_record_id, media, queued_sms_message)
        return rl

    @api.model
    def check_all_messages(self):
        """Check for any messages that might have been missed during server downtime"""
        my_accounts = self.env['sms.account'].search([])
        for sms_account in my_accounts:
            self.env[sms_account.account_gateway_id.gateway_model_name].check_messages(sms_account.id)
