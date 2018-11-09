# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools


class TestMassSMS(models.TransientModel):
    _name = "test.mass.sms"

    recipient_ids = fields.Many2many('sms.list', 'test_mass_sms_list_rel', 'test_mass_sms_id', 'test_list_id', string='Recipients')

    def get_recipients(self):
        self.ensure_one()
        recipient = recipients = self.env['sms.recipients']
        for list in self.recipient_ids:
            recipients |= recipient.search([('sms_list_id', '=', list.id)])
        return recipients

    @api.multi
    def send_sms(self):
        self.ensure_one()
        context = dict(self.env.context or {})
        active_id = context.get('active_id')
        record = self.env['mass.sms'].browse(active_id)

        SmsCompose = self.env['sms.compose']
        recipients = self.get_recipients()
        for recipient in recipients:
            if recipient.partner_id.mobile:
                render_msg = self.env['sms.template'].render_template(record.sms_template_id.template_body, 'res.partner', recipient.partner_id.id)
                message = tools.html2plaintext(render_msg)
                msg_compose = SmsCompose.create({
                    'record_id': recipient.partner_id.id,
                    'model': 'res.partner',
                    'sms_template_id': record.sms_template_id.id,
#                     'from_mobile_id': self.env.ref('sms_frame.sms_number_inuka_international').id,
                    'from_mobile_id': record.from_mobile_id.id,
                    'to_number': recipient.partner_id.mobile,
                    'sms_content': message,
                })
                msg_compose.send_entity()

        return {'type': 'ir.actions.act_window_close'}
