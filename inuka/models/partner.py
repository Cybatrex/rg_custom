# -*- coding: utf-8 -*-

import random
import string
import re
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from random import randint
import logging
from lxml import etree
from odoo.osv.orm import setup_modifiers
from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.exceptions import ValidationError
from odoo.tools import email_split
from odoo.addons.auth_signup.models.res_partner import SignupError, now

_logger = logging.getLogger(__name__)


class Users(models.Model):
    _inherit = "res.users"

    @api.model
    def create(self, vals):
        return super(Users, self.with_context(from_user=True)).create(vals)

    @api.model
    def reset_password(self, login):
        """ retrieve the user corresponding to login (login or email),
            and reset their password
        """
        users = self.search([('login', '=', login)])
        if not users:
            users = self.search([('email', '=', login)])
        if len(users) != 1:
            raise Exception(_('Reset password: invalid username or email'))
        return users.action_reset_password()


    @api.multi
    def action_reset_password(self):
        """ create signup token for each user, and send their signup url by email """
        # prepare reset password signup
        create_mode = bool(self.env.context.get('create_user'))

        # no time limit for initial invitation, only for reset password
        expiration = False if create_mode else now(days=+1)

        self.mapped('partner_id').signup_prepare(signup_type="reset", expiration=expiration)

        # send email to users with their signup url
        template = False
        if create_mode:
            try:
                template = self.env.ref('auth_signup.set_password_email', raise_if_not_found=False)
            except ValueError:
                pass
        if not template:
            template = self.env.ref('auth_signup.reset_password_email')
        assert template._name == 'mail.template'

        for user in self:
            if user.email and self.env.context.get('reset_via_mail'):
                template.with_context(lang=user.lang).send_mail(user.id, force_send=True, raise_exception=True)
                _logger.info("Password reset email sent for user <%s> to <%s>", user.login, user.email)
            if user.partner_id.mobile and self.env.context.get('reset_via_sms'):
                user.send_reset_sms()

    @api.multi
    def send_reset_sms(self):
        self.ensure_one()
        sms_template = self.env.ref('sms_frame.sms_template_reset_password')
        msg_compose = self.env['sms.compose'].create({
            'record_id': self.id,
            'model': 'res.users',
            'sms_template_id': sms_template.id,
            'from_mobile_id': sms_template.from_mobile_verified_id.id,
            'to_number': self.partner_id.mobile,
            'sms_content': """Dear %s, A password reset was requested for your Inuka Portal/Mobile App. Change your password by following this link which is valid for 24 hrs:
%s""" % (self.name, self.partner_id.signup_url)
        })
        msg_compose.send_entity()


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False,
                        submenu=False):
        res = super(ResPartner, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar,
            submenu=submenu)
        
        bulk_group_id = self.env.ref('inuka.bulk_group').id
        data_group_id = self.env.ref('inuka.data_group').id
        user_group_ids = self.env['res.users'].browse(self._uid).groups_id.ids
        
        if view_type == 'form':

            if bulk_group_id in user_group_ids or data_group_id in user_group_ids:
                doc = etree.XML(res['arch'])
                nodes_candidate_registrar = doc.xpath("//field[@name='candidate_registrar']")[0]
                nodes_candidate_registrar.set('readonly', '0')
                setup_modifiers(nodes_candidate_registrar)

                nodes_up_front_kits = doc.xpath("//field[@name='up_front_kits']")[0]
                nodes_up_front_kits.set('readonly', '0')
                setup_modifiers(nodes_up_front_kits)

                nodes_bulk_custodian = doc.xpath("//field[@name='bulk_custodian']")[0]
                nodes_bulk_custodian.set('readonly', '0')
                setup_modifiers(nodes_bulk_custodian)
                res['arch'] = etree.tostring(doc)
        return res

    def _default_candidate(self):
        if self.customer:
            return 'candidate'
        return False

    @api.onchange('customer')
    def _default_candidate(self):
        if self.customer and not self.status:
            self.status = 'candidate'

    @api.model
    def default_credit_limit(self):
        if not self.env.context.get('parent_id'):
            return 100000

    first_name = fields.Char("First Name")
    last_name = fields.Char("Last Name")
    passport_no = fields.Char("ID/Passport No")
    home_phone = fields.Char("Home Phone")
    join_date = fields.Date("Join Date")
    dob = fields.Date("DOB")
    available_bal = fields.Float(string="Balance", compute="_compute_balance_available", store=False)
    available_fund = fields.Float(string="Available Funds", compute="_compute_balance_available", store=False)
    is_available = fields.Boolean(compute="_compute_is_available", store=True)
    is_credit_adjustment_group = fields.Boolean(compute="_compute_credit_adjustment_group")
    credit_limit = fields.Float(default=default_credit_limit)

    def _compute_credit_adjustment_group(self):
        for partner in self:
            if partner.user_has_groups('inuka.credit_adjustment_group'):
                partner.is_credit_adjustment_group = True
            else:
                partner.is_credit_adjustment_group = False

    @api.depends('available_bal')
    def _compute_is_available(self):
        for partner in self:
            if partner.available_bal > 0:
                partner.is_available = True
            else:
                partner.is_available = False

    @api.multi
    def _compute_balance_available(self):
        for partner in self:
            reserved_fund = self.env['reserved.fund'].search([('customer_id', '=', partner.id)])

            select = ',COALESCE(SUM(\"account_move_line\".debit-\"account_move_line\".credit), 0),SUM(\"account_move_line\".debit),SUM(\"account_move_line\".credit)'

            sql = "SELECT \"account_move_line\".partner_id%s FROM %s WHERE %s%s AND \"account_move_line\".partner_id IS NOT NULL GROUP BY \"account_move_line\".partner_id"
            tables, where_clause, where_params = self.env['account.move.line']._query_get([('move_id.state', '=', 'posted'), ('account_id.internal_type', 'in', ('receivable', 'payable'))])
            line_clause = partner and ' AND \"account_move_line\".partner_id = ' + str(partner.id) or ''

            query = sql % (select, tables, where_clause, line_clause)
            self.env.cr.execute(query, where_params)
            results = self.env.cr.fetchall()
            results = dict([(k[0], {'balance': k[1], 'debit': k[2], 'credit': k[3]}) for k in results])

            # bal = results.get(partner.id).get('balance', 0.0) if results else 0.0
            cr = results.get(partner.id).get('credit', 0.0) if results else 0.0
            dr = results.get(partner.id).get('debit', 0.0) if results else 0.0
            available_balance = dr - cr
            if available_balance > 0:
                partner.available_bal = -available_balance
                bal_avl = -available_balance
            else:
                partner.available_bal = abs(available_balance)
                bal_avl = abs(available_balance)

            partner.available_fund = bal_avl - sum(reserved_fund.mapped('amount'))

    @api.multi
    def open_customer_ledger(self):
        return {'type': 'ir.actions.client',
            'name': _('Partner Ledger'),
            'tag': 'account_report',
            'options': {'partner_id': self.id},
            'ignore_session': 'both',
            'context': "{'model':'account.partner.ledger'}"} 
    
            
    status = fields.Selection([
        ('candidate', 'Candidate'),
        ('new', 'New'),
        ('junior', 'Junior'),
        ('senior', 'Senior'),
        ('pearl', 'Pearl'),
        ('ruby', 'Ruby'),
        ('emerald', 'Emerald'),
        ('sapphire', 'Sapphire'),
        ('diamond', 'Diamond'),
        ('double_diamond', 'Double Diamond'),
        ('triple_diamond', 'Triple Diamond'),
        ('exective_diamond', 'Exective Diamond'),
        ('presidential', 'Presidential'),
        ('cancelled', 'Cancelled'),
        ('discontinued', 'Discontinued')
        ], string='Status', default=_default_candidate, track_visibility='onchange')
    upline = fields.Many2one("res.partner", string="Upline")
    upline_id = fields.Char(related="upline.ref", string="Upline ID")
    candidate_registrar = fields.Boolean("Candidate Registrar")
    compute_field = fields.Boolean(string="check field", compute='get_user')
    bulk_custodian = fields.Boolean("Bulk Custodian")
    up_front_kits = fields.Boolean("Up-front Kits")
    personal_pv = fields.Float("Personal PV")
    pv_downline_1 = fields.Float("PV Downline 1")
    pv_downline_2 = fields.Float("PV Downline 2")
    pv_downline_3 = fields.Float("PV Downline 3")
    pv_downline_4 = fields.Float("PV Downline 4")
    pv_tot_group = fields.Float("PV Tot Group")
    personal_members = fields.Integer("Active Personal Members")
    new_members = fields.Integer("New Members")
    kit = fields.Selection([
        ('small', 'Small Kit'),
        ('medium', 'Medium Kit'),
        ('large', 'Large Kit'),
        ('junior', 'Junior kit'),
        ('senior', 'Senior kit'),
        ('not_indicated', 'Kit Not Indicated')
        ], string='Kit')
    source = fields.Selection([
        ('email', 'Email'),
        ('facebook', 'Facebook'),
        ('fax', 'Fax'),
        ('inuka', 'Inuka'),
        ('phone', 'Phone'),
        ('sms', 'SMS'),
        ('whatsapp', 'Whatsapp'),
        ('portal', 'Portal')
        ], string='Source', required=True, default='email')
    is_admin = fields.Boolean(compute="_compute_is_admin", string="Admin")
    is_active_mtd = fields.Boolean("Is Active (MTD)")
    is_new_mtd = fields.Boolean("Is New (MTD)")
    is_vr_earner_mtd = fields.Boolean("Is VR Earner (MTD)")
    is_new_senior_mtd = fields.Boolean("Is New & Senior Beyond (MTD)")
    is_new_junior_mtd = fields.Boolean("Is New & Junior Beyond (MTD)")
    is_new_ruby_mtd = fields.Boolean("Is New & Ruby & Beyond (MTD)")
    vr_earner = fields.Integer("# of VR Earners (MTD)")
    new_senior_recruits = fields.Integer("# of New Senior Recruits (MTD)")
    new_junior_recruits = fields.Integer("# of New Junior Recruits (MTD)")

    # QTD Performance Tab
    personal_pv_qtd = fields.Float("Personal PV (QTD)")
    pv_downline_1_qtd = fields.Float("PV Downline 1 (QTD)")
    pv_downline_2_qtd = fields.Float("PV Downline 2 (QTD)")
    pv_downline_3_qtd = fields.Float("PV Downline 3 (QTD)")
    pv_downline_4_qtd = fields.Float("PV Downline 4 (QTD)")
    pv_tot_group_qtd = fields.Float("Group PV (QTD)")
    personal_members_qtd = fields.Integer("# of Active Downline (QTD)")
    new_members_qtd = fields.Integer("# of New Members (QTD)")

    is_active_qtd = fields.Boolean("Is Active (QTD)")
    is_new_qtd = fields.Boolean("Is New (QTD)")
    is_vr_earner_qtd = fields.Boolean("Is VR Earner (QTD)")
    is_new_senior_qtd = fields.Boolean("Is New & Senior Beyond (QTD)")
    is_new_junior_qtd = fields.Boolean("Is New & Junior Beyond (QTD))")
    is_new_ruby_qtd = fields.Boolean("Is New & Ruby & Beyond (QTD)")
    vr_earner_qtd = fields.Integer("# of VR Earners (QTD)")
    new_senior_recruits_qtd = fields.Integer("# of New Senior Recruits (QTD)")
    new_junior_recruits_qtd = fields.Integer("# of New Junior Recruits (QTD)")

    # YTD Performance Tab
    personal_pv_ytd = fields.Float("Personal PV (YTD)")
    pv_downline_1_ytd = fields.Float("PV Downline 1 (YTD)")
    pv_downline_2_ytd = fields.Float("PV Downline 2 (YTD)")
    pv_downline_3_ytd = fields.Float("PV Downline 3 (YTD)")
    pv_downline_4_ytd = fields.Float("PV Downline 4 (YTD)")
    pv_tot_group_ytd = fields.Float("Group PV (YTD)")
    personal_members_ytd = fields.Integer("# of Active Downline (YTD)")
    new_members_ytd = fields.Integer("# of New Members (YTD)")

    is_active_ytd = fields.Boolean("Is Active (YTD)")
    is_new_ytd = fields.Boolean("Is New (YTD)")
    is_vr_earner_ytd = fields.Boolean("Is VR Earner (YTD)")
    is_new_senior_ytd = fields.Boolean("Is New & Senior Beyond (YTD)")
    is_new_junior_ytd = fields.Boolean("Is New & Junior Beyond (YTD))")
    is_new_ruby_ytd = fields.Boolean("Is New & Ruby & Beyond (YTD)")
    vr_earner_ytd = fields.Integer("# of VR Earners (YTD)")
    new_senior_recruits_ytd = fields.Integer("# of New Senior Recruits (YTD)")
    new_junior_recruits_ytd = fields.Integer("# of New Junior Recruits (YTD)")

    # MTD Odoo Tab
    o_personal_pv_mtd = fields.Float(compute="_compute_mtd", string="O_Personal PV (MTD)")
    o_pv_downline_1_mtd = fields.Float(compute="_compute_mtd", string="O_PV Downline 1 (MTD)")
    o_pv_downline_2_mtd = fields.Float(compute="_compute_mtd", string="O_PV Downline 2 (MTD)")
    o_pv_downline_3_mtd = fields.Float(compute="_compute_mtd", string="O_PV Downline 3 (MTD)")
    o_pv_downline_4_mtd = fields.Float(compute="_compute_mtd", string="O_PV Downline 4 (MTD)")
    o_pv_tot_group_mtd = fields.Float(compute="_compute_mtd", string="O_Group PV (MTD)")
    o_personal_members_mtd = fields.Integer(compute="_compute_mtd", string="O_# of Active Downline (MTD)")
    o_new_members_mtd = fields.Integer(compute="_compute_mtd", string="O_# of New Members (MTD)")

    o_is_active_mtd = fields.Boolean(compute="_compute_mtd", string="O_Is Active (MTD)")
    o_is_new_mtd = fields.Boolean(compute="_compute_mtd", string="O_Is New (MTD)")
    o_is_vr_earner_mtd = fields.Boolean(compute="_compute_mtd", string="O_Is VR Earner (MTD)")
    o_is_new_senior_mtd = fields.Boolean(compute="_compute_mtd", string="O_Is New & Senior Beyond (MTD)")
    o_is_new_junior_mtd = fields.Boolean(compute="_compute_mtd", string="O_Is New & Junior Beyond (MTD))")
    o_is_new_ruby_mtd = fields.Boolean(compute="_compute_mtd", string="O_Is New & Ruby & Beyond (MTD)")
    o_vr_earner_mtd = fields.Integer(compute="_compute_mtd", string="O_# of VR Earners (MTD)")
    o_new_senior_recruits_mtd = fields.Integer(compute="_compute_mtd", string="O_# of New Senior Recruits (MTD)")
    o_new_junior_recruits_mtd = fields.Integer(compute="_compute_mtd", string="O_# of New Junior Recruits (MTD)")

    # QTD Odoo Tab
    o_personal_pv_qtd = fields.Float(compute="_compute_qtd", string="O_Personal PV (QTD)")
    o_pv_downline_1_qtd = fields.Float(compute="_compute_qtd", string="O_PV Downline 1 (QTD)")
    o_pv_downline_2_qtd = fields.Float(compute="_compute_qtd", string="O_PV Downline 2 (QTD)")
    o_pv_downline_3_qtd = fields.Float(compute="_compute_qtd", string="O_PV Downline 3 (QTD)")
    o_pv_downline_4_qtd = fields.Float(compute="_compute_qtd", string="O_PV Downline 4 (QTD)")
    o_pv_tot_group_qtd = fields.Float(compute="_compute_qtd", string="O_Group PV (QTD)")
    o_personal_members_qtd = fields.Integer(compute="_compute_qtd", string="O_# of Active Downline (QTD)")
    o_new_members_qtd = fields.Integer(compute="_compute_qtd", string="O_# of New Members (QTD)")

    o_is_active_qtd = fields.Boolean(compute="_compute_qtd", string="O_Is Active (QTD)")
    o_is_new_qtd = fields.Boolean(compute="_compute_qtd", string="O_Is New (QTD)")
    o_is_vr_earner_qtd = fields.Boolean(compute="_compute_qtd", string="O_Is VR Earner (QTD)")
    o_is_new_senior_qtd = fields.Boolean(compute="_compute_qtd", string="O_Is New & Senior Beyond (QTD)")
    o_is_new_junior_qtd = fields.Boolean(compute="_compute_qtd", string="O_Is New & Junior Beyond (QTD))")
    o_is_new_ruby_qtd = fields.Boolean(compute="_compute_qtd", string="O_Is New & Ruby & Beyond (QTD)")
    o_vr_earner_qtd = fields.Integer(compute="_compute_qtd", string="O_# of VR Earners (QTD)")
    o_new_senior_recruits_qtd = fields.Integer(compute="_compute_qtd", string="O_# of New Senior Recruits (QTD)")
    o_new_junior_recruits_qtd = fields.Integer(compute="_compute_qtd", string="O_# of New Junior Recruits (QTD)")

    # YTD Odoo Tab
    o_personal_pv_ytd = fields.Float(compute="_compute_ytd", string="O_Personal PV (YTD)")
    o_pv_downline_1_ytd = fields.Float(compute="_compute_ytd", string="O_PV Downline 1 (YTD)")
    o_pv_downline_2_ytd = fields.Float(compute="_compute_ytd", string="O_PV Downline 2 (YTD)")
    o_pv_downline_3_ytd = fields.Float(compute="_compute_ytd", string="O_PV Downline 3 (YTD)")
    o_pv_downline_4_ytd = fields.Float(compute="_compute_ytd", string="O_PV Downline 4 (YTD)")
    o_pv_tot_group_ytd = fields.Float(compute="_compute_ytd", string="O_Group PV (YTD)")
    o_personal_members_ytd = fields.Integer(compute="_compute_ytd", string="O_# of Active Downline (YTD)")
    o_new_members_ytd = fields.Integer(compute="_compute_ytd", string="O_# of New Members (YTD)")

    o_is_active_ytd = fields.Boolean(compute="_compute_ytd", string="O_Is Active (YTD)")
    o_is_new_ytd = fields.Boolean(compute="_compute_ytd", string="O_Is New (YTD)")
    o_is_vr_earner_ytd = fields.Boolean(compute="_compute_ytd", string="O_Is VR Earner (YTD)")
    o_is_new_senior_ytd = fields.Boolean(compute="_compute_ytd", string="O_Is New & Senior Beyond (YTD)")
    o_is_new_junior_ytd = fields.Boolean(compute="_compute_ytd", string="O_Is New & Junior Beyond (YTD))")
    o_is_new_ruby_ytd = fields.Boolean(compute="_compute_ytd", string="O_Is New & Ruby & Beyond (YTD)")
    o_vr_earner_ytd = fields.Integer(compute="_compute_ytd", string="O_# of VR Earners (YTD)")
    o_new_senior_recruits_ytd = fields.Integer(compute="_compute_ytd", string="O_# of New Senior Recruits (YTD)")
    o_new_junior_recruits_ytd = fields.Integer(compute="_compute_ytd", string="O_# of New Junior Recruits (YTD)")

    performance_history_count = fields.Integer(compute="_compute_performance_history_count", string="Performance History Count")
    rewards_count = fields.Integer(compute="_compute_rewards_count", string="Rewards Count")
    downline_count = fields.Integer(compute="_compute_downline_count", string="Downline Count")
    project_count = fields.Integer(compute="_compute_project_count", string="Project Count")
    sms_count = fields.Integer(compute="_compute_sms_count", string="SMS Count")
    property_product_pricelist = fields.Many2one(track_visibility='onchange')
    watchlist = fields.Boolean('Watchlist', default=False)

    device_id = fields.Char("Device ID", readonly=True)
    device_type = fields.Selection([
        ('android', 'Android'),
        ('iphone', 'iPhone'),
    ], string="Device Type", readonly=True)
    is_device_live = fields.Boolean("Is Device Live", readonly=True)
    mobile = fields.Char("Mobile", default=27)
#     portal_password = fields.Char("Portal Password")

    _sql_constraints = [
#         ('mobile_uniq', 'unique(mobile)', 'Mobile should be unique.'),
        ('email_uniq', 'unique(email)', 'Email should be unique.'),
        ('ref_uniq', 'unique(ref)', 'Internal Reference should be unique.'),
    ]

    def get_user(self):
        for user in self:
            res_user = self.env['res.users'].search([('id', '=', user._uid)])
            if res_user.has_group('inuka.data_group') or res_user.has_group('inuka.bulk_group'):
                user.compute_field = False
            else:
                user.compute_field = True
        
    @api.multi
    def fund_transfer(self):
        action = self.env.ref('inuka.action_fund_transfer_form_view').read()[0]
        action['context'] = {'default_partner_id': self.id, 'from_partner': True}
        return action
        

    @api.model
    def get_month_interval(self, current_date):
        first_date = current_date.replace(day=7)
        next_first_date = current_date + relativedelta(day=1, months=1)  # Getting 1st of next month
        last_date = next_first_date.replace(day=6)
        return first_date, last_date

    @api.multi
#     @api.depends('invoice_ids', 'invoice_ids.type', 'invoice_ids.date_invoice', 'invoice_ids.state',\
#                  'upline', 'customer', 'status')
    @api.depends()
    def _compute_mtd(self):
        return

        Invoice = self.env['account.invoice']
        first_date, last_date = self.get_month_interval(date.today())
        for partner in self:
            invoices = Invoice.search([('partner_id', '=', partner.id), ('type', '=', 'out_invoice'), ('date_invoice', '>=', first_date), ('date_invoice', '<=', last_date), ('state', 'not in', ('draft', 'cancel'))])
            personal_pv_month = sum(invoices.mapped('total_pv'))

            partner.o_personal_pv_mtd = personal_pv_month

            downline1_partner = partner.search([('upline', '=', partner.id), ('customer', '=', True)])
            downline1_invoices = Invoice.search([('partner_id', 'in', downline1_partner.ids), ('type', '=', 'out_invoice'), ('date_invoice', '>=', first_date), ('date_invoice', '<=', last_date), ('state', 'not in', ('draft', 'cancel'))])
            pv_downline_1_month = sum(downline1_invoices.mapped('total_pv'))
            partner.o_pv_downline_1_mtd = pv_downline_1_month

            downline2_partner = partner.search([('upline', 'in', downline1_partner.ids), ('customer', '=', True)])
            downline2_invoices = Invoice.search([('partner_id', 'in', downline2_partner.ids), ('type', '=', 'out_invoice'), ('date_invoice', '>=', first_date), ('date_invoice', '<=', last_date), ('state', 'not in', ('draft', 'cancel'))])
            pv_downline_2_month = sum(downline2_invoices.mapped('total_pv'))
            partner.o_pv_downline_2_mtd = pv_downline_2_month

            downline3_partner = partner.search([('upline', 'in', downline2_partner.ids), ('customer', '=', True)])
            downline3_invoices = Invoice.search([('partner_id', 'in', downline3_partner.ids), ('type', '=', 'out_invoice'), ('date_invoice', '>=', first_date), ('date_invoice', '<=', last_date), ('state', 'not in', ('draft', 'cancel'))])
            pv_downline_3_month = sum(downline3_invoices.mapped('total_pv'))
            partner.o_pv_downline_3_mtd = pv_downline_3_month

            downline4_partner = partner.search([('upline', 'in', downline3_partner.ids), ('customer', '=', True)])
            downline4_invoices = Invoice.search([('partner_id', 'in', downline4_partner.ids), ('type', '=', 'out_invoice'), ('date_invoice', '>=', first_date), ('date_invoice', '<=', last_date), ('state', 'not in', ('draft', 'cancel'))])
            pv_downline_4_month = sum(downline4_invoices.mapped('total_pv'))
            partner.o_pv_downline_4_mtd = pv_downline_4_month

            group_pv_month = personal_pv_month + pv_downline_1_month + pv_downline_2_month + pv_downline_3_month + pv_downline_4_month
            partner.o_pv_tot_group_mtd = group_pv_month

            is_active_month = False
            if personal_pv_month >= 5:
                is_active_month = True
            partner.o_is_active_mtd = is_active_month

            is_new_month = False
            join_date = fields.Date.from_string(partner.join_date)
            if join_date and join_date >= first_date and join_date <= last_date:
                is_new_month = True
            partner.o_is_new_mtd = is_new_month

            is_vr_earner_month = False
            if personal_pv_month >= 20 and group_pv_month >= 45:
                is_vr_earner_month = True
            partner.o_is_vr_earner_mtd = is_vr_earner_month

            is_new_senior_month = False
            if is_new_month == True and partner.status in ('senior', 'pearl', 'ruby', 'emerald', 'sapphire', 'diamond', 'double_diamond', 'triple_diamond', 'exective_diamond', 'presidential'):
                is_new_senior_month = True
            partner.o_is_new_senior_mtd = is_new_senior_month

            is_new_junior_month = False
            if is_new_month == True and partner.status in ('junior', 'senior', 'pearl', 'ruby', 'emerald', 'sapphire', 'diamond', 'double_diamond', 'triple_diamond', 'exective_diamond', 'presidential'):
                is_new_junior_month = True
            partner.o_is_new_junior_mtd = is_new_junior_month

            is_new_ruby_month = False
            if is_new_month == True and partner.status in ('ruby', 'emerald', 'sapphire', 'diamond', 'double_diamond', 'triple_diamond', 'exective_diamond', 'presidential'):
                is_new_ruby_month = True
            partner.o_is_new_ruby_mtd = is_new_ruby_month

            # partner.o_personal_members_mtd = len(downline1_partner.filtered(lambda partner: partner.o_is_active_mtd)) # of Active Downline (MTD)
            # partner.o_new_members_mtd = len(downline1_partner.filtered(lambda partner: partner.o_is_new_mtd)) # of New Members (MTD)
            # partner.o_vr_earner_mtd = len(downline1_partner.filtered(lambda partner: partner.o_is_vr_earner_mtd)) # of VR Earners (MTD)
            # partner.o_new_senior_recruits_mtd = len(downline1_partner.filtered(lambda partner: partner.o_is_new_mtd and partner.status in ('senior', 'pearl', 'ruby', 'emerald', 'sapphire', 'diamond', 'double_diamond', 'triple_diamond','exective_diamond', 'presidential'))) # of New Senior Recruits (MTD)
            # partner.o_new_junior_recruits_mtd = len(downline1_partner.filtered(lambda partner: partner.o_is_new_mtd and partner.status in ('junior','senior', 'pearl', 'ruby', 'emerald', 'sapphire', 'diamond', 'double_diamond', 'triple_diamond','exective_diamond', 'presidential'))) # of New Junior Recruits (MTD)

    @api.model
    def get_quarter_interval(self, current_date):
        if current_date.month < 6 or (current_date.month == 6 and current_date.day < 7):
            current_year = current_date.year - 1
        elif current_date.month > 6 or (current_date.month == 6 and current_date.day > 6):
            current_year = current_date.year

        q1_start_date = date(current_year, 6, 7)
        q1_end_date = date(current_year, 9, 6)
        if current_date >= q1_start_date and current_date <= q1_end_date:
            return q1_start_date, q1_end_date

        q2_start_date = date(current_year, 9, 7)
        q2_end_date = date(current_year, 12, 6)
        if current_date >= q2_start_date and current_date <= q2_end_date:
            return q2_start_date, q2_end_date

        q3_start_date = date(current_year, 12, 7)
        q3_end_date = date(current_year + 1, 3, 6)
        if current_date >= q3_start_date and current_date <= q3_end_date:
            return q3_start_date, q3_end_date

        q4_start_date = date(current_year + 1, 3, 7)
        q4_end_date = date(current_year + 1, 6, 6)
        if current_date >= q4_start_date and current_date <= q4_end_date:
            return q4_start_date, q4_end_date

    @api.multi
    @api.depends()
    def _compute_qtd(self):
        return

        Invoice = self.env['account.invoice']
        first_date, last_date = self.get_quarter_interval(date.today())
        for partner in self:
            invoices = Invoice.search([('partner_id', '=', partner.id), ('type', '=', 'out_invoice'), ('date_invoice', '>=', first_date), ('date_invoice', '<=', last_date), ('state', 'not in', ('draft', 'cancel'))])
            personal_pv_quarter = sum(invoices.mapped('total_pv'))
            partner.o_personal_pv_qtd = personal_pv_quarter

            downline1_partner = partner.search([('upline', '=', partner.id), ('customer', '=', True)])
            downline1_invoices = Invoice.search([('partner_id', 'in', downline1_partner.ids), ('type', '=', 'out_invoice'), ('date_invoice', '>=', first_date), ('date_invoice', '<=', last_date), ('state', 'not in', ('draft', 'cancel'))])
            pv_downline_1_quarter = sum(downline1_invoices.mapped('total_pv'))
            partner.o_pv_downline_1_qtd = pv_downline_1_quarter

            downline2_partner = partner.search([('upline', 'in', downline1_partner.ids), ('customer', '=', True)])
            downline2_invoices = Invoice.search([('partner_id', 'in', downline2_partner.ids), ('type', '=', 'out_invoice'), ('date_invoice', '>=', first_date), ('date_invoice', '<=', last_date), ('state', 'not in', ('draft', 'cancel'))])
            pv_downline_2_quarter = sum(downline2_invoices.mapped('total_pv'))
            partner.o_pv_downline_2_qtd = pv_downline_2_quarter

            downline3_partner = partner.search([('upline', 'in', downline2_partner.ids), ('customer', '=', True)])
            downline3_invoices = Invoice.search([('partner_id', 'in', downline3_partner.ids), ('type', '=', 'out_invoice'), ('date_invoice', '>=', first_date), ('date_invoice', '<=', last_date), ('state', 'not in', ('draft', 'cancel'))])
            pv_downline_3_quarter = sum(downline3_invoices.mapped('total_pv'))
            partner.o_pv_downline_3_qtd = pv_downline_3_quarter

            downline4_partner = partner.search([('upline', 'in', downline3_partner.ids), ('customer', '=', True)])
            downline4_invoices = Invoice.search([('partner_id', 'in', downline4_partner.ids), ('type', '=', 'out_invoice'), ('date_invoice', '>=', first_date), ('date_invoice', '<=', last_date), ('state', 'not in', ('draft', 'cancel'))])
            pv_downline_4_quarter = sum(downline4_invoices.mapped('total_pv'))
            partner.o_pv_downline_4_qtd = pv_downline_4_quarter

            group_pv_quarter = personal_pv_quarter + pv_downline_1_quarter + pv_downline_2_quarter + pv_downline_3_quarter + pv_downline_4_quarter
            partner.o_pv_tot_group_qtd = group_pv_quarter

            is_active_quarter = False
            if personal_pv_quarter >= 15:
                is_active_quarter = True
            partner.o_is_active_qtd = is_active_quarter

            is_new_quarter = False
            join_date = fields.Date.from_string(partner.join_date)
            if join_date and join_date >= first_date and join_date <= last_date:
                is_new_quarter = True
            partner.o_is_new_qtd = is_new_quarter

            is_vr_earner_quarter = False
            if personal_pv_quarter >= 60 and group_pv_quarter >= 135:
                is_vr_earner_quarter = True
            partner.o_is_vr_earner_qtd = is_vr_earner_quarter

            is_new_senior_quarter = False
            if is_new_quarter == True and partner.status in ('senior', 'pearl', 'ruby', 'emerald', 'sapphire', 'diamond', 'double_diamond', 'triple_diamond', 'exective_diamond', 'presidential'):
                is_new_senior_quarter = True
            partner.o_is_new_senior_qtd = is_new_senior_quarter

            is_new_junior_quarter = False
            if is_new_quarter == True and partner.status in ('junior', 'senior', 'pearl', 'ruby', 'emerald', 'sapphire', 'diamond', 'double_diamond', 'triple_diamond', 'exective_diamond', 'presidential'):
                is_new_junior_quarter = True
            partner.o_is_new_junior_qtd = is_new_junior_quarter

            is_new_ruby_quarter = False
            if is_new_quarter == True and partner.status in ('ruby', 'emerald', 'sapphire', 'diamond', 'double_diamond', 'triple_diamond', 'exective_diamond', 'presidential'):
                is_new_ruby_quarter = True
            partner.o_is_new_ruby_qtd = is_new_ruby_quarter

            # partner.o_personal_members_qtd = len(downline1_partner.filtered(lambda partner: partner.o_is_active_qtd)) # of Active Downline (QTD)
            # partner.o_new_members_qtd = len(downline1_partner.filtered(lambda partner: partner.o_is_new_qtd)) # of New Members (QTD)
            # partner.o_vr_earner_qtd = len(downline1_partner.filtered(lambda partner: partner.o_is_vr_earner_qtd)) # of VR Earners (QTD)
            # partner.o_new_senior_recruits_qtd = len(downline1_partner.filtered(lambda partner: partner.o_is_new_qtd and partner.status in ('senior', 'pearl', 'ruby', 'emerald', 'sapphire', 'diamond', 'double_diamond', 'triple_diamond','exective_diamond', 'presidential'))) # of New Senior Recruits (QTD)
            # partner.o_new_junior_recruits_qtd = len(downline1_partner.filtered(lambda partner: partner.o_is_new_qtd and partner.status in ('junior','senior', 'pearl', 'ruby', 'emerald', 'sapphire', 'diamond', 'double_diamond', 'triple_diamond','exective_diamond', 'presidential'))) # of New Junior Recruits (QTD)

    @api.model
    def get_year_interval(self, current_date):
        if current_date.month < 6 or (current_date.month == 6 and current_date.day < 7):
            current_year = current_date.year - 1
        elif current_date.month > 6 or (current_date.month == 6 and current_date.day > 6):
            current_year = current_date.year

        start_date = date(current_year, 6, 7)
        end_date = date(current_year + 1, 6, 6)
        return start_date, end_date

    @api.multi
    @api.depends()
    def _compute_ytd(self):
        return

        Invoice = self.env['account.invoice']
        first_date, last_date = self.get_year_interval(date.today())
        for partner in self:
            invoices = Invoice.search([('partner_id', '=', partner.id), ('type', '=', 'out_invoice'), ('date_invoice', '>=', first_date), ('date_invoice', '<=', last_date), ('state', 'not in', ('draft', 'cancel'))])
            personal_pv_year = sum(invoices.mapped('total_pv'))
            partner.o_personal_pv_ytd = personal_pv_year

            downline1_partner = partner.search([('upline', '=', partner.id), ('customer', '=', True)])
            downline1_invoices = Invoice.search([('partner_id', 'in', downline1_partner.ids), ('type', '=', 'out_invoice'), ('date_invoice', '>=', first_date), ('date_invoice', '<=', last_date), ('state', 'not in', ('draft', 'cancel'))])
            pv_downline_1_year = sum(downline1_invoices.mapped('total_pv'))
            partner.o_pv_downline_1_ytd = pv_downline_1_year

            downline2_partner = partner.search([('upline', 'in', downline1_partner.ids), ('customer', '=', True)])
            downline2_invoices = Invoice.search([('partner_id', 'in', downline2_partner.ids), ('type', '=', 'out_invoice'), ('date_invoice', '>=', first_date), ('date_invoice', '<=', last_date), ('state', 'not in', ('draft', 'cancel'))])
            pv_downline_2_year = sum(downline2_invoices.mapped('total_pv'))
            partner.o_pv_downline_2_ytd = pv_downline_2_year

            downline3_partner = partner.search([('upline', 'in', downline2_partner.ids), ('customer', '=', True)])
            downline3_invoices = Invoice.search([('partner_id', 'in', downline3_partner.ids), ('type', '=', 'out_invoice'), ('date_invoice', '>=', first_date), ('date_invoice', '<=', last_date), ('state', 'not in', ('draft', 'cancel'))])
            pv_downline_3_year = sum(downline3_invoices.mapped('total_pv'))
            partner.o_pv_downline_3_ytd = pv_downline_3_year

            downline4_partner = partner.search([('upline', 'in', downline3_partner.ids), ('customer', '=', True)])
            downline4_invoices = Invoice.search([('partner_id', 'in', downline4_partner.ids), ('type', '=', 'out_invoice'), ('date_invoice', '>=', first_date), ('date_invoice', '<=', last_date), ('state', 'not in', ('draft', 'cancel'))])
            pv_downline_4_year = sum(downline4_invoices.mapped('total_pv'))
            partner.o_pv_downline_4_ytd = pv_downline_4_year

            group_pv_year = personal_pv_year + pv_downline_1_year + pv_downline_2_year + pv_downline_3_year + pv_downline_4_year
            partner.o_pv_tot_group_ytd = group_pv_year

            is_active_year = False
            if personal_pv_year >= 60:
                is_active_year = True
            partner.o_is_active_ytd = is_active_year

            is_new_year = False
            join_date = fields.Date.from_string(partner.join_date)
            if join_date and join_date >= first_date and join_date <= last_date:
                is_new_year = True
            partner.o_is_new_ytd = is_new_year

            is_vr_earner_year = False
            if personal_pv_year >= 160 and group_pv_year >= 540:
                is_vr_earner_year = True
            partner.o_is_vr_earner_ytd = is_vr_earner_year

            is_new_senior_year = False
            if is_new_year == True and partner.status in ('senior', 'pearl', 'ruby', 'emerald', 'sapphire', 'diamond', 'double_diamond', 'triple_diamond', 'exective_diamond', 'presidential'):
                is_new_senior_year = True
            partner.o_is_new_senior_ytd = is_new_senior_year

            is_new_junior_year = False
            if is_new_year == True and partner.status in ('junior', 'senior', 'pearl', 'ruby', 'emerald', 'sapphire', 'diamond', 'double_diamond', 'triple_diamond', 'exective_diamond', 'presidential'):
                is_new_junior_year = True
            partner.o_is_new_junior_ytd = is_new_junior_year

            is_new_ruby_year = False
            if is_new_year == True and partner.status in ('ruby', 'emerald', 'sapphire', 'diamond', 'double_diamond', 'triple_diamond', 'exective_diamond', 'presidential'):
                is_new_ruby_year = True
            partner.o_is_new_ruby_ytd = is_new_ruby_year

            # partner.o_personal_members_ytd = len(downline1_partner.filtered(lambda partner: partner.o_is_active_ytd)) # of Active Downline (YTD)
            # partner.o_new_members_ytd = len(downline1_partner.filtered(lambda partner: partner.o_is_new_ytd)) # of New Members (YTD)
            # partner.o_vr_earner_ytd = len(downline1_partner.filtered(lambda partner: partner.o_is_vr_earner_ytd)) # of VR Earners (YTD)
            # partner.o_new_senior_recruits_ytd = len(downline1_partner.filtered(lambda partner: partner.o_is_new_ytd and partner.status in ('senior', 'pearl', 'ruby', 'emerald', 'sapphire', 'diamond', 'double_diamond', 'triple_diamond','exective_diamond', 'presidential'))) # of New Senior Recruits (YTD)
            # partner.o_new_junior_recruits_ytd = len(downline1_partner.filtered(lambda partner: partner.o_is_new_ytd and partner.status in ('junior','senior', 'pearl', 'ruby', 'emerald', 'sapphire', 'diamond', 'double_diamond', 'triple_diamond','exective_diamond', 'presidential'))) # of New Junior Recruits (YTD)
    @api.depends()
    def _compute_is_admin(self):
        for partner in self:
            if partner.env.user._is_superuser():
                partner.is_admin = True
            else:
                partner.is_admin = False

    @api.constrains('dob')
    def _check_dob(self):
        for partner in self:
            if partner.dob:
                dob = datetime.strptime(partner.dob, DF)
                today = date.today()
                age = relativedelta(today, dob)
                if age.years < 18:
                    raise ValidationError(_('Member should be 18 years and above.'))

    @api.constrains('mobile')
    def _check_mobile(self):
        if self._context.get('from_user'):
            return
        else:
            for partner in self:
                if partner.mobile:
                    if ' ' in partner.mobile:
                        raise ValidationError(_('Mobile Number should not have any space.'))
                    mobile = partner.mobile.replace(' ', '')
                    if len(mobile) < 11:
                        raise ValidationError(_('Mobile Number should not be less than 11 digits.'))
                    if self.search_count([('mobile', '=', partner.mobile), ('parent_id', '=', False)]) > 1:
                        raise ValidationError(_('Mobile should be unique.'))

    @api.onchange('first_name', 'last_name')
    def _onchange_first_name(self):
        if self.customer:
            name = ''
            if self.first_name:
                name += (self.first_name)
            if self.last_name:
                name += ' ' + (self.last_name)
            if self.ref:
                name += ' (' + (self.ref) + ')'
            self.name = name

    def _prepare_sale_order(self):
        self.ensure_one()

        kit = self.kit
        vals = {
            'small': 600.00,
            'medium': 1300.00,
            'large': 1800.00,
            'junior': 3000.00,
            'senior': 6000.00,
            'not_indicated': 0.00,
        }
        order_total = vals.get(kit, 0.00)

        product_vals = {
            'small': 'KITSM',
            'medium': 'KITMD',
            'large': 'KITLG',
            'junior': 'KITJR',
            'senior': 'KITSR'
        }
        default_code = product_vals.get(kit)
        product = self.env['product.product']
        if default_code:
            product = product.search([('default_code', '=', default_code)], limit=1)

        team_id = self.env['crm.team'].search([('name', '=', 'Registrations')], limit=1)
        pos_team = self.env['crm.team'].search([('name', '=', 'Point of Sale')], limit=1)
        if self.env.user in pos_team.member_ids:
            warehouse = self.env['stock.warehouse'].search([('name', '=', 'Bellpark')], limit=1).id
        else:
            warehouse = self.env['stock.warehouse'].search([('name', '=', '8 Vrede Street')], limit=1).id
        return {
            'partner_id': self.id,
            'kit_order': True,
            'order_sent_by': self.source,
            'sale_date': self.join_date,
            'order_type': 'single',
            'pricelist_id': self.property_product_pricelist.id,
            'carrier_id': False,
            'payment_term_id': self.env.ref('account.account_payment_term_immediate').id,
            'pv': product.categ_id.category_pv,
            'order_total': order_total,
            'product_cost': order_total,
            'picking_policy': 'one',
            'user_id': self.create_uid.id,
            'client_order_ref': kit,
            'company_id': self.company_id.id,
            'team_id': team_id.id if team_id else False,
            'warehouse_id': warehouse or self.env['stock.warehouse'].search([], limit=1).id,
        }

    def _prepare_sale_order_line(self, order):
        self.ensure_one()

        vals = {
            'small': 'KITSM',
            'medium': 'KITMD',
            'large': 'KITLG',
            'junior': 'KITJR',
            'senior': 'KITSR'
        }
        default_code = vals.get(self.kit)
        product = self.env['product.product']
        if default_code:
            product = product.search([('default_code', '=', default_code)], limit=1)

        if not product:
            return {}
        return {
            'product_id': product.id,
            'product_uom_qty': 1.0,
            'order_id': order.id,
            'pv': product.pv,
            'unit_pv': product.pv,
        }

    @api.model
    def create(self, vals):
        context = dict(self.env.context or {})
        if vals.get('customer') and not context.get('from_user', False):
            first_name = vals.get('first_name', '')
            last_name = vals.get('last_name', '')
#             if not vals.get('ref'):
#                 vals['ref'] = ''.join(random.choice(string.ascii_letters).upper() for x in range(3)) + (str(randint(100,999)))
            vals['name'] = ''
            if first_name:
                vals['name'] += (first_name)
            if last_name:
                vals['name'] += ' ' + (last_name)
            if vals.get('ref'):
                 vals['name'] += ' (' + (vals.get('ref')) + ')'
            if not vals.get('status'):
                vals['status'] = 'candidate'
        res = super(ResPartner, self).create(vals)
        if self._context.get('from_user'):
            res.mobile = ''
        if res.customer and not context.get('from_user', False):
            sale_order_vals = res._prepare_sale_order()
            order = self.env['sale.order'].with_context(kit_order=True).create(sale_order_vals)
            sale_order_line_vals = res._prepare_sale_order_line(order)
            if sale_order_line_vals:
                self.env['sale.order.line'].create(sale_order_line_vals)

            if res.mobile:
                sms_template = self.env.ref('sms_frame.sms_template_inuka_international')
                msg_compose = self.env['sms.compose'].create({
                    'record_id': res.id,
                    'model': 'res.partner',
                    'sms_template_id': sms_template.id,
                    'from_mobile_id': self.env.ref('sms_frame.sms_number_inuka_international').id,
                    'to_number': res.mobile,
                    'sms_content': """ INUKA Welcomes YOU^Thank you for your Registration^ %s %s,your MemberID %s will be active once Kit payment is receipted^More info 27219499850""" % (res.first_name, res.last_name, res.ref)
                })
                msg_compose.send_entity()

            if res.upline.mobile:
                sms_template = self.env.ref('sms_frame.sms_template_inuka_international_referrer')
                msg_compose = self.env['sms.compose'].create({
                    'record_id': res.upline.id,
                    'model': 'res.partner',
                    'sms_template_id': sms_template.id,
                    'from_mobile_id': self.env.ref('sms_frame.sms_number_inuka_international').id,
                    'to_number': res.upline.mobile,
                    'sms_content': """ INUKA New Registration received^WELL DONE, %s^New MemberID %s for %s %s activated once kit is receipted^Info 27219499850""" % (res.upline.name, res.ref, res.first_name, res.last_name)
                })
                msg_compose.send_entity()

            # related_partner = self.env['portal.wizard'].create({'user_ids': [(0,0,{'partner_id': res.id,'email': res.email, 'in_portal': True})]})
            # related_partner.action_apply()
        return res

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.search(['|', '|', '|', '|', ('ref', operator, name), ('name', operator, name), ('mobile', operator, name), ('passport_no', operator, name), ('email', operator, name)] + args, limit=limit)
        return recs.name_get()

    @api.model
    def check_birthday(self):
        customers = self.search([('customer', '=', True), ('status', 'in', ('new', 'junior', 'senior', 'pearl', 'ruby'))])
        today = datetime.today()
        for customer in customers:
            if customer.dob and customer.mobile:
                dob = datetime.strptime(customer.dob, DF)
                if dob.day == today.day and dob.month == today.month:
                    sms_template = self.env.ref('sms_frame.sms_template_inuka_international')
                    msg_compose = self.env['sms.compose'].create({
                        'record_id': customer.id,
                        'model': 'res.partner',
                        'sms_template_id': sms_template.id,
                        'from_mobile_id': self.env.ref('sms_frame.sms_number_inuka_international').id,
                        'to_number': customer.mobile,
                        'sms_content': """ INUKA Happy Birthday %s %s, sending you SMILES for every moment of your special day. Have a wonderful HAPPY BIRTHDAY. Your INUKA Team 27219499850""" % (customer.first_name, customer.last_name)
                    })
                    msg_compose.send_entity()

    @api.model
    def create_birthday_ticket(self):
        HelpDeskTicket = self.env['helpdesk.ticket']
        team = self.env['helpdesk.team'].search([('name', '=', 'Escalations')], limit=1)
        ticket_type = self.env['helpdesk.ticket.type'].search([('name', '=', 'Birthday')], limit=1)
        channel = self.env['mail.channel'].search([('name', '=', 'Escalations')], limit=1)
        customers = self.search([('customer', '=', True), ('status', 'in', ('emerald', 'sapphire', 'diamond', 'double_diamond', 'triple_diamond', 'exective_diamond', 'presidential'))])
        today = datetime.today() + relativedelta(days=1)
        for customer in customers:
            if customer.dob:
                dob = datetime.strptime(customer.dob, DF)
                if dob.day == today.day and dob.month == today.month:
                    ticket = HelpDeskTicket.create({
                        'name': """Birthday: %s %s - %s""" % (customer.first_name, customer.last_name, customer.dob),
                        'team_id': team.id,
                        'user_id': False,
                        'priority': '2',
                        'description': """Birthday: %s %s - %s""" % (customer.first_name, customer.last_name, customer.dob),
                        'partner_id': customer.id,
                        'mobile': customer.mobile,
                        'partner_email': customer.email,
                        'ticket_type_id': ticket_type.id,
                    })
                    if channel:
                        ticket.message_subscribe(channel_ids=[channel.id])

    @api.multi
    def create_helpdesk_ticket(self):
        HelpDeskTicket = self.env['helpdesk.ticket']
        team = self.env['helpdesk.team'].search([('name', '=', 'Escalations')], limit=1)
        ticket_type = self.env['helpdesk.ticket.type'].search([('name', '=', 'Other')], limit=1)
        channel = self.env['mail.channel'].search([('name', '=', 'Escalations')], limit=1)
        tag = self.env['helpdesk.tag'].search([('name', '=', 'Status Change')], limit=1)
        user = self.env['res.users'].search([('login', '=', 'alma@inuka.co.za')], limit=1)
        stage = self.env['helpdesk.stage'].search([('name', '=', 'New')], limit=1)
        for customer in self:
            ticket = HelpDeskTicket.create({
                'name': """%s %s has achieved %s status""" % (customer.first_name, customer.last_name, customer.status),
                'team_id': team.id,
                'user_id': user.id,
                'priority': '2',
                'description': """%s %s has achieved %s status""" % (customer.first_name, customer.last_name, customer.status),
                'partner_id': customer.id,
                'mobile': customer.mobile,
                'partner_email': customer.email,
                'ticket_type_id': ticket_type.id,
                'tag_ids': [(6, 0, tag.ids)],
                'stage_id': stage.id,
            })
            ticket.message_subscribe(channel_ids=[channel.id])
    
    @api.depends()
    def _compute_performance_history_count(self):
        PerformanceHistory = self.env['performance.history']
        for partner in self:
            partner.performance_history_count = PerformanceHistory.search_count([('partner_id', '=', partner.id)])
    
    @api.depends()
    def _compute_downline_count(self):
        for partner in self:
            partner.downline_count = partner.search_count([('upline', '=', partner.id), ('customer', '=', True)])

    @api.depends()
    def _compute_project_count(self):
        Project = self.env['project.project']
        for partner in self:
            partner.project_count = Project.search_count([('partner_id', '=', partner.id)])

    @api.depends()
    def _compute_sms_count(self):
        SmsMessage = self.env['sms.message']
        model_id = self.env['ir.model'].search([('model', '=', 'res.partner')], limit=1).id
        for partner in self:
            partner.sms_count = SmsMessage.search_count([('model_id', '=', model_id), ('record_id', '=', partner.id)])

    @api.multi
    def view_performance_history(self):
        self.ensure_one()
        performances = self.env['performance.history'].search([('partner_id', '=', self.id)])
        action = self.env.ref('inuka.action_performance_history_form').read()[0]
        action['domain'] = [('id', 'in', performances.ids)]
        return action

    @api.depends()
    def _compute_rewards_count(self):
        Rewards = self.env['inuka.reward']
        for partner in self:
            partner.rewards_count = Rewards.search_count([('partner_id', '=', partner.id)])

    @api.multi
    def view_rewards(self):
        self.ensure_one()
        rewards = self.env['inuka.reward'].search([('partner_id', '=', self.id)])
        action = self.env.ref('inuka.action_inuka_rewards_form').read()[0]
        action['domain'] = [('id', 'in', rewards.ids)]
        return action

    @api.multi
    def view_downline_member(self):
        self.ensure_one()
        partners = self.search([('upline', '=', self.id), ('customer', '=', True)])
        view_id = self.env.ref('inuka.view_res_partner_downline_tree').id

        return {
            'name': _('Downline'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree',
            'res_model': 'res.partner',
            'view_id': view_id,
            'context': self.env.context,
            'domain': [('id', 'in', partners.ids)],
        }

    @api.multi
    def view_project(self):
        self.ensure_one()
        projects = self.env['project.project'].search([('partner_id', '=', self.id)])
        action = self.env.ref('project.open_view_project_all').read()[0]
        action['domain'] = [('id', 'in', projects.ids)]
        return action

    @api.multi
    def view_sms_message(self):
        self.ensure_one()
        model_id = self.env['ir.model'].search([('model', '=', 'res.partner')], limit=1).id
        messages = self.env['sms.message'].search([('model_id', '=', model_id), ('record_id', '=', self.id)])

        return {
            'name': _('Messages'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'sms.message',
            'context': self.env.context,
            'domain': [('id', 'in', messages.ids)],
        }

    @api.multi
    def action_watchlist_add(self):
        self.ensure_one()
        watchlist_comment_id = self.env.ref('inuka.view_partner_watchlist_comment_form').id
        return {
            'name': _('Watchlist Comment'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'res.partner.watchlist',
            'views': [(watchlist_comment_id, 'form')],
            'view_id': watchlist_comment_id,
            'target': 'new',
            'context': {'watchlist': False},
        }

    @api.multi
    def action_watchlist_remove(self):
        self.ensure_one()
        watchlist_comment_id = self.env.ref('inuka.view_partner_watchlist_comment_form').id
        return {
            'name': _('Watchlist Comment'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'res.partner.watchlist',
            'views': [(watchlist_comment_id, 'form')],
            'view_id': watchlist_comment_id,
            'target': 'new',
            'context': {'watchlist': True},
        }


class PerformanceHistory(models.Model):
    _name = 'performance.history'
    _description = 'Performance History'
    _rec_name = 'partner_id'

    partner_id = fields.Many2one("res.partner", string="Customer")
    performance_type = fields.Selection([
        ('month', 'Month Performance'),
        ('quarter', 'Quarter Performance'),
        ('year', 'Year Performance'),
        ], string='Type')
    date = fields.Date("Date", default=fields.Date.today())
    months = fields.Selection([
        ('jan', 'January'),
        ('feb', 'February'),
        ('mar', 'March'),
        ('apr', 'April'),
        ('may', 'May'),
        ('jun', 'June'),
        ('jul', 'July'),
        ('aug', 'August'),
        ('sep', 'September'),
        ('oct', 'October'),
        ('nov', 'November'),
        ('dec', 'December')
        ], string='Month')
    quarters = fields.Selection([
        ('q1', 'Q1'),
        ('q2', 'Q2'),
        ('q3', 'Q3'),
        ('q4', 'Q4'),
        ], string='Quarter')
    years = fields.Selection([
        ('2016', '2016'),
        ('2017', '2017'),
        ('2018', '2018'),
        ('2019', '2019'),
        ('2020', '2020'),
        ('2021', '2021'),
        ('2022', '2022')
        ], string='Year')

    status = fields.Selection([
        ('candidate', 'Candidate'),
        ('new', 'New'),
        ('junior', 'Junior'),
        ('senior', 'Senior'),
        ('pearl', 'Pearl'),
        ('ruby', 'Ruby'),
        ('emerald', 'Emerald'),
        ('sapphire', 'Sapphire'),
        ('diamond', 'Diamond'),
        ('double_diamond', 'Double Diamond'),
        ('triple_diamond', 'Triple Diamond'),
        ('exective_diamond', 'Exective Diamond'),
        ('presidential', 'Presidential'),
        ('discontinued', 'Discontinued'),
        ], string='Status', default='candidate')

    personal_pv = fields.Float("Personal PV")
    pv_downline_1 = fields.Float("PV Downline 1")
    pv_downline_2 = fields.Float("PV Downline 2")
    pv_downline_3 = fields.Float("PV Downline 3")
    pv_downline_4 = fields.Float("PV Downline 4")
    pv_tot_group = fields.Float("Group PV")
    personal_members = fields.Integer("# of Active Downline")
    new_members = fields.Integer("# of New Members")

    is_active = fields.Boolean("Is Active")
    is_new = fields.Boolean("Is New")
    is_vr_earner = fields.Boolean("Is VR Earner")
    is_new_senior = fields.Boolean("Is New & Senior Beyond")
    is_new_junior = fields.Boolean("Is New & Junior Beyond")
    is_new_ruby = fields.Boolean("Is New & Ruby & Beyond")
    vr_earner = fields.Integer("# of VR Earners")
    new_senior_recruits = fields.Integer("# of New Senior Recruits")
    new_junior_recruits = fields.Integer("# of New Junior Recruits")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)


def extract_email(email):
    """ extract the email address from a user-friendly email address """
    addresses = email_split(email)
    return addresses[0] if addresses else ''


class PortalWizardUser(models.TransientModel):
    _inherit = 'portal.wizard.user'

    @api.multi
    def action_apply(self):
        self.env['res.partner'].check_access_rights('write')
        """ From selected partners, add corresponding users to chosen portal group. It either granted
            existing user, or create new one (and add it to the group).
        """

        for wizard_user in self.sudo().with_context(active_test=False):
            if not wizard_user.partner_id.email:
                return True
            group_portal = wizard_user.wizard_id.portal_id
            if not group_portal.is_portal:
                raise UserError(_('Group %s is not a portal') % group_portal.name)
            user = wizard_user.partner_id.user_ids[0] if wizard_user.partner_id.user_ids else None
            # update partner email, if a new one was introduced
            if wizard_user.partner_id.email != wizard_user.email:
                wizard_user.partner_id.write({'email': wizard_user.email})
            # add portal group to relative user of selected partners
            if wizard_user.in_portal:
                user_portal = None
                # create a user if necessary, and make sure it is in the portal group
                if not user:
                    if wizard_user.partner_id.company_id:
                        company_id = wizard_user.partner_id.company_id.id
                    else:
                        company_id = self.env['res.company']._company_default_get('res.users')
                    user_portal = wizard_user.sudo().with_context(company_id=company_id)._create_user()
                else:
                    user_portal = user
                wizard_user.write({'user_id': user_portal.id})
                if not wizard_user.user_id.active or group_portal not in wizard_user.user_id.groups_id:
                    wizard_user.user_id.write({'active': True, 'groups_id': [(4, group_portal.id)]})
                    # prepare for the signup process
                    wizard_user.user_id.partner_id.signup_prepare()
                    wizard_user.with_context(active_test=True)._send_email()
                wizard_user.refresh()
            else:
                # remove the user (if it exists) from the portal group
                if user and group_portal in user.groups_id:
                    # if user belongs to portal only, deactivate it
                    if len(user.groups_id) <= 1:
                        user.write({'groups_id': [(3, group_portal.id)], 'active': False})
                    else:
                        user.write({'groups_id': [(3, group_portal.id)]})


    @api.multi
    def _create_user(self):
        """ create a new user for wizard_user.partner_id
            :returns record of res.users
        """
        partner = self.partner_id
        company_id = self.env.context.get('company_id')
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': partner.name,
            'email': extract_email(self.email),
            'login': partner.ref,
            'password': partner.ref,
            'partner_id': self.partner_id.id,
            'company_id': company_id,
            'company_ids': [(6, 0, [company_id])],
            'groups_id': [(6, 0, [])],
        })
        
        

