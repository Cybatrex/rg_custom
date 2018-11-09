# -*- coding: utf-8 -*-

from odoo import models, fields, api

class inuka_pos(models.Model):
	_inherit = 'pos.config'

	reserve_fund_account_id = fields.Many2one('account.journal', string='Reserve Fund Account', domain=[('journal_user', '=', 1)])

	@api.model
	def calculate_reserve(self, partner_id):
		res_funds = self.env['reserved.fund'].search([('customer_id', '=', partner_id)])
		partner = self.env['res.partner'].search([('id', '=', partner_id)])
		amount_reserve = sum([x.amount for x in res_funds])
		return - (partner.credit - partner.debit) + partner.credit_limit - amount_reserve
