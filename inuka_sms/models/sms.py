# -*- coding: utf-8 -*-

from datetime import datetime

from odoo import api, fields, models, tools
import urllib3
import logging
_logger = logging.getLogger(__name__)

class SmsList(models.Model):
    _name = 'sms.list'
    _description = 'SMS List'

    name = fields.Char(string="Name")
    var1 = fields.Char("VAR 1")
    var2 = fields.Char("VAR 2")
    var3 = fields.Char("VAR 3")
    var4 = fields.Char("VAR 4")
    var5 = fields.Char("VAR 5")
    var6 = fields.Char("VAR 6")
    description = fields.Text()
    active = fields.Boolean(default=True)
    sms_recipients_count = fields.Integer(compute="_compute_sms_recipients_count", string="Number of Recipients")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)

    def _compute_sms_recipients_count(self):
        SmsRecipients = self.env['sms.recipients']
        for record in self:
            record.sms_recipients_count = SmsRecipients.search_count([('sms_list_id', '=', record.id)])

    @api.multi
    def view_sms_recipients(self):
        self.ensure_one()
        recipients = self.env['sms.recipients'].search([('sms_list_id', '=', self.id)])
        action = self.env.ref('inuka_sms.action_sms_recipients_form').read()[0]
        action['domain'] = [('id', 'in', recipients.ids)]
        action['context'] = {'default_sms_list_id': self.id}
        return action


class SmsRecipients(models.Model):
    _name = 'sms.recipients'
    _description = 'SMS Recipients'

    name = fields.Char(string="Name")
    partner_id = fields.Many2one("res.partner", string="Member")
    member_id = fields.Char(related="partner_id.ref", string="Member ID")
    mobile = fields.Char()
    var1 = fields.Char("VAR 1")
    var2 = fields.Char("VAR 2")
    var3 = fields.Char("VAR 3")
    var4 = fields.Char("VAR 4")
    var5 = fields.Char("VAR 5")
    var6 = fields.Char("VAR 6")
    unsubscription_date = fields.Datetime("Unsubscription Date")
    optout = fields.Boolean("Opt Out")
    sms_list_id = fields.Many2one("sms.list", string="SMS List")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)

    @api.onchange('partner_id', 'mobile')
    def _onchange_member(self):
        if not self.partner_id and not self.mobile:
            return
        self.name = self.partner_id.name or self.mobile


class MassSms(models.Model):
    _name = 'mass.sms'
    _description = 'Mass SMS'

    name = fields.Char(string="Name")
    from_mobile_id = fields.Many2one("sms.number", string="From")
    recipient_ids = fields.Many2many('sms.list', 'mass_sms_list_rel', 'mass_sms_id', 'list_id', string='Recipients')
    sms_template_id = fields.Many2one("sms.template", string="Template")
    sms_content = fields.Text("SMS Body")
    scheduled_date = fields.Datetime("Scheduled Date")
    sent_date = fields.Datetime(string='Sent Date', copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('queue', 'In Queue'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('cancelled', 'Cancelled')
        ], string='Status', default='draft', track_visibility='onchange')
    batch_mode = fields.Boolean("Batch Mode")
    batch_size = fields.Integer("Batch Size", default=1000)
    sent_ratio = fields.Integer(compute="_compute_statistics", string="SMS Sent's")
    pending_ratio = fields.Integer(compute="_compute_statistics", string="SMS Pending")
    received_ratio = fields.Integer(compute="_compute_statistics", string="SMS Received")
    errors_ratio = fields.Integer(compute="_compute_statistics", string="Errors")
    total = fields.Integer(compute="_compute_statistics")
    sent = fields.Integer(compute="_compute_statistics")
    pending = fields.Integer(compute="_compute_statistics")
    received = fields.Integer(compute="_compute_statistics")
    errors = fields.Integer(compute="_compute_statistics")
    next_departure = fields.Datetime(compute="_compute_next_departure", string='Scheduled date')
    participants = fields.One2many('sms.participant', 'mass_sms_id', string="Participants")
    sms_participant_count = fields.Integer(compute="_compute_sms_participant_count", string="Number of Participants")
    participant_generated = fields.Boolean(copy=False)
    color = fields.Integer()
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)

    def _compute_statistics(self):
        SmsMessage = self.env['sms.message']
        for record in self:
            total = len(record.participants) or 1
            pending = len(record.participants.filtered(lambda r: r.state == 'running'))
            sent = len(record.participants.filtered(lambda r: r.state == 'completed'))
            received = len(SmsMessage.search([('mass_sms_id', '=', record.id), ('status_code', 'in', ('003', '004'))]))
            errors = len(SmsMessage.search([('mass_sms_id', '=', record.id), ('status_code', 'in', ('001', '002', '005', '006', '007', '009', '010', '011', '012', '013', '014'))]))

            record.pending_ratio = 100 * pending / total
            record.sent_ratio = 100 * sent / total
            record.received_ratio = 100 * received / total
            record.errors_ratio = 100 * errors / total

            record.total = len(record.participants)
            record.sent = sent
            record.pending = pending
            record.received = received
            record.errors = errors

    def _compute_sms_participant_count(self):
        for record in self:
            record.sms_participant_count = len(record.participants)

    def _compute_next_departure(self):
        cron_next_call = self.env.ref('inuka_sms.ir_cron_mass_sms_queue').sudo().nextcall
        str2dt = fields.Datetime.from_string
        cron_time = str2dt(cron_next_call)
        for mass_sms in self:
            if mass_sms.schedule_date:
                schedule_date = str2dt(mass_sms.schedule_date)
                mass_sms.next_departure = max(schedule_date, cron_time)
            else:
                mass_sms.next_departure = cron_time

    @api.onchange('sms_template_id')
    def _onchange_sms_template_id(self):
        self.sms_content = self.sms_template_id.template_body

    @api.multi
    def get_remaining_recipients(self):
        self.ensure_one()
        return self.participants.filtered(lambda r: r.state == 'running')

    @api.model
    def _process_mass_sms_queue(self):
        mass_sms = self.search([('state', 'in', ('queue', 'sending')), '|', ('scheduled_date', '<', fields.Datetime.now()), ('scheduled_date', '=', False)])
        for sms in mass_sms:
            if len(sms.get_remaining_recipients()) > 0:
                sms.state = 'sending'
                sms.send_sms()
            else:
                sms.state = 'sent'

    def send_sms(self):
        self.ensure_one()
        SmsCompose = self.env['sms.compose']
        participants = self.get_remaining_recipients()
        for participant in participants[:self.batch_size]:
            if participant.partner_id.mobile:
                render_msg = self.env['sms.template'].render_template(self.sms_template_id.template_body, self.sms_template_id.model_id.model, participant.partner_id.id)
                message = tools.html2plaintext(render_msg)
                msg_compose = SmsCompose.create({
                    'record_id': participant.partner_id.id,
                    'model': 'res.partner',
                    'sms_template_id': self.sms_template_id.id,
                    'from_mobile_id': self.from_mobile_id.id,
                    'to_number': participant.partner_id.mobile,
                    'sms_content': message,
                })
                msg_compose.with_context(mass_sms_id=self.id).send_entity()
            participant.state = 'completed'

    @api.multi
    def generate_participants(self):
        participant = self.env['sms.participant']
        recipient = self.env['sms.recipients']
        for record in self:
            if not record.participant_generated:
                for list in record.recipient_ids:
                    recipients = recipient.search([('sms_list_id', '=', list.id)])
                    for recipient in recipients:
                        participant.create({'partner_id': recipient.partner_id.id, 'mass_sms_id': record.id})
                record.participant_generated = True

    @api.multi
    def view_participants(self):
        self.ensure_one()
        action = self.env.ref('inuka_sms.action_sms_participant_form').read()[0]
        action['domain'] = [('id', 'in', self.participants.ids)]
        return action

    @api.multi
    def view_stastics(self):
        return True

    @api.multi
    def open_received_sms_message(self):
        self.ensure_one()
        messages = self.env['sms.message'].search([('mass_sms_id', '=', self.id), ('status_code', 'in', ('003', '004'))])
        action = self.env.ref('inuka_sms.action_sms_message_form_outbound').read()[0]
        action['domain'] = [('id', 'in', messages.ids)]
        action['view_mode'] = 'tree,form'
        return action

    @api.multi
    def open_error_sms_message(self):
        self.ensure_one()
        messages = self.env['sms.message'].search([('mass_sms_id', '=', self.id), ('status_code', 'in', ('001', '002', '005', '006', '007', '009', '010', '011', '012', '013', '014'))])
        action = self.env.ref('inuka_sms.action_sms_message_form_outbound').read()[0]
        action['domain'] = [('id', 'in', messages.ids)]
        action['view_mode'] = 'tree,form'
        return action

    @api.multi
    def button_send_all(self):
        self.write({'sent_date': fields.Datetime.now(), 'state': 'queue'})

    @api.multi
    def button_cancel(self):
        self.mapped('participants').write({'state': 'cancelled'})
        self.write({'state': 'cancelled'})


class SmsParticipant(models.Model):
    _name = 'sms.participant'
    _description = 'SMS Participant'
    _rec_name = 'partner_id'

    partner_id = fields.Many2one("res.partner", string="Member")
    mass_sms_id = fields.Many2one('mass.sms', string='Mass SMS', ondelete='cascade', required=True)
    state = fields.Selection([
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
        ], default='running', index=True, required=True,
    )
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)


class SmsShortcode(models.Model):
    _name = 'sms.shortcode'
    _description = 'SMS Shortcode'
    _rec_name = 'keyword'

    keyword = fields.Char("Keyword")
    sms_template_id = fields.Many2one("sms.template", string="Template")
    member_required = fields.Boolean("Member Required")
    active = fields.Boolean(default=True)
    no_member_sms_template_id = fields.Many2one("sms.template", string="No Member SMS Template")


class SmsMessage(models.Model):
    _inherit = "sms.message"

    keyword = fields.Char("Keyword")
    mass_sms_id = fields.Many2one("mass.sms", string="Mass SMS")
    status_code = fields.Selection([
        ('001','Message unknown'),
        ('002', 'Message queued'),
        ('003', 'Delivered to gateway'),
        ('004', 'Received by recipient'),
        ('005', 'Error with message'),
        ('006','User cancelled message delivery'),
        ('007', 'Error delivering message'),
        ('009', 'Routing error'),
        ('010', 'Message expired'),
        ('011', 'Message scheduled for later delivery'),
        ('012', 'Out of credit'),
        ('013', 'Clickatell cancelled message delivery'),
        ('014', 'Maximum MT limit exceeded'),
        ], string='Delivary State', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)

    @api.multi
    def send_sms_reply(self):
        SmsShortcode = self.env['sms.shortcode']
        ResPartner = self.env['res.partner']
        SmsCompose = self.env['sms.compose']
        for message in self:
            shortcode = SmsShortcode.search([('keyword', '=', message.keyword)], limit=1)
            if shortcode and shortcode.member_required and message.model_id.model == 'res.partner':
                partner = ResPartner.browse(message.record_id)
                if partner.mobile:
                    render_msg = self.env['sms.template'].render_template(shortcode.sms_template_id.template_body, 'res.partner', partner.id)
                    message = tools.html2plaintext(render_msg)
                    msg_compose = SmsCompose.create({
                        'record_id': partner.id,
                        'model': 'res.partner',
                        'sms_template_id': shortcode.sms_template_id.id,
                        'from_mobile_id': self.env.ref('sms_frame.sms_number_inuka_international').id,
                        'to_number': partner.mobile,
                        'sms_content': message,
                    })
                    msg_compose.send_entity()
            elif shortcode and shortcode.member_required and message.model_id.model != 'res.partner':
                if message.from_mobile:
                    msg_compose = SmsCompose.create({
                        'record_id': message.record_id,
                        'model': message.model_id.model,
                        'sms_template_id': shortcode.no_member_sms_template_id.id,
                        'from_mobile_id': self.env.ref('sms_frame.sms_number_inuka_international').id,
                        'to_number': message.from_mobile,
                        'sms_content': shortcode.no_member_sms_template_id.template_body,
                    })
                    msg_compose.send_entity()
            elif shortcode and not shortcode.member_required:
                msg_compose = SmsCompose.create({
                    'record_id': message.record_id,
                    'model': message.model_id.model,
                    'sms_template_id': shortcode.sms_template_id.id,
                    'from_mobile_id': self.env.ref('sms_frame.sms_number_inuka_international').id,
                    'to_number': message.from_mobile,
                    'sms_content': shortcode.sms_template_id.template_body,
                })
                msg_compose.send_entity()


class SmsCompose(models.Model):
    _inherit = "sms.compose"

    @api.model
    def create(self, vals):
        if vals is None:
            vals = {}
        SmsAccount = self.env['sms.account']
        SmsNumber = self.env['sms.number']
        to_number = vals.get('to_number')
        if to_number:
            if to_number.startswith('27'):
                sms_account = SmsAccount.search([('international', '=', False)], limit=1)
            else:
                sms_account = SmsAccount.search([('international', '=', True)], limit=1)
            if not sms_account:
                sms_account = SmsAccount.search([], limit=1)
            from_mobile = SmsNumber.search([('account_id', '=', sms_account.id)], limit=1)
            vals['from_mobile_id'] = from_mobile.id
        return super(SmsCompose, self).create(vals)

    @api.multi
    def send_entity(self):
        """Attempt to send the sms, if any error comes back show it to the user and only log the smses that successfully sent"""
        self.ensure_one()
        #gateway_model = self.from_mobile_id.account_id.account_gateway_id.gateway_model_name
        my_sms = self.from_mobile_id.account_id.send_message(self.from_mobile_id.mobile_number, self.to_number, self.sms_content.encode('utf-8'), self.model, self.record_id, self.media_id)[0]
        error_message = my_sms['error']

        #display the screen with an error code if the sms/mms was not successfully sent
        if my_sms['errorCode'] != False:
            return {
               'type':'ir.actions.act_window',
               'res_model':'sms.compose',
               'view_type':'form',
               'view_mode':'form',
               'target':'new',
               'context':{'default_to_number':self.to_number,'default_record_id':self.record_id,'default_model':self.model, 'default_error_message':error_message}
            }
        else:
            my_model = self.env['ir.model'].search([('model','=',self.model)])

        #for single smses we only record succesful sms, failed ones reopen the form with the error message
        sms_message = self.env['sms.message'].create({
            'record_id': self.record_id,
            'model_id': my_model[0].id,
            'account_id': self.from_mobile_id.account_id.id,
            'from_mobile': self.from_mobile_id.mobile_number,
            'to_mobile': self.to_number,
            'sms_content': self.sms_content,
            'status_string': my_sms['error'],
            'direction': 'O',
            'message_date': datetime.utcnow(),
            'status_code': my_sms['errorCode'],
            'sms_gateway_message_id': my_sms['id'],
            'by_partner_id': self.env.user.partner_id.id,
            'mass_sms_id': self.env.context.get('mass_sms_id'),
        })
        sms_subtype = self.env['ir.model.data'].get_object('sms_frame', 'sms_subtype')
        attachments = []
        if self.media_id:
            attachments.append((self.media_filename, base64.b64decode(self.media_id)) )
        self.env[self.model].search([('id','=', self.record_id)]).message_post(body=self.sms_content, subject="SMS Sent", message_type="comment", subtype_id=sms_subtype.id, attachments=attachments)


class SmsAccount(models.Model):
    _inherit = "sms.account"

    active = fields.Boolean(default=True)
    international = fields.Boolean()
