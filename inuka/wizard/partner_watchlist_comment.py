# -*- coding: utf-8 -*-

from odoo import fields, models, _


class PartnerWatchlist(models.TransientModel):
    _name = "res.partner.watchlist"

    comment = fields.Text(string="comment", required=True)

    def action_watchlist_comment(self):
        partner = self.env['res.partner'].browse(self.env.context.get('active_id'))
        if self.env.context.get('watchlist'):
            partner.watchlist = False
            message = _("%s removed from watchlist. Comment: %s") % (partner.name, self.comment)
            partner.message_post(body=message)
        else:
            partner.watchlist = True
            message = _("%s added to watchlist. Comment: %s") % (partner.name, self.comment)
            partner.message_post(body=message)
