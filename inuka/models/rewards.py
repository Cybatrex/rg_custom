# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class InukaRewards(models.Model):
    _name = 'inuka.reward'
    _description = "Rewards"

    partner_id = fields.Many2one("res.partner", string="Member", required=True, track_visibility='always')
    date = fields.Datetime("Date", readonly=True, required=True, default=fields.Datetime.now(), copy=False)
    quarters = fields.Selection([('q1', 'Q1'), ('q2', 'Q2'), ('q3', 'Q3'), ('q4', 'Q4')], string='Quarter')
    category_id = fields.Many2one('reward.category', string='Category')
    achievement_level_id = fields.Many2one('achievement.level', string='Achievement Level')
    cash = fields.Float(string='Cash')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    reward_type = fields.Selection([('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('annual', 'Annual')], string='Type')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id)


class RewardCategory(models.Model):
    _name = 'reward.category'
    _description = "Reward Category"

    name = fields.Char('Name', index=True, required=True, translate=True)


class AchievementLevel(models.Model):
    _name = 'achievement.level'
    _description = "Achievement Level"

    name = fields.Char('Name', index=True, required=True, translate=True)
