# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api
import logging
_logger = logging.getLogger(__name__)
from lxml import etree
from odoo.osv.orm import setup_modifiers
from datetime import datetime, date


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    pv = fields.Float("PV's", readonly=True)
    sale_date = fields.Date(string="Sale Date", readonly=True)
    amount_total = fields.Float(string="Total Including Tax", readonly=True)

    def get_object(self):
        _logger.info(["KKKKKKKKKKKKKKKKKKK", self._ids])
        #self._context.update({})

    def _select(self):
        select_str = super(AccountInvoiceReport,self)._select()
        select_str += """ ,sub.pv
                          ,sub.sale_date
                          ,sub.amount_total as amount_total"""
        return select_str

    def _sub_select(self):
        sub_select_str = super(AccountInvoiceReport,self)._sub_select()
        sub_select_str += """ ,ail.pv as pv
                              ,ai.sale_date as sale_date
                              ,sum(ail.price_total) as amount_total"""
                              
        return sub_select_str

    def _group_by(self):
        group_by_str = super(AccountInvoiceReport,self)._group_by()
        group_by_str += """,ail.pv
                           ,ai.sale_date
                           ,ai.amount_total
                            """
        return group_by_str

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False,
                        submenu=False):
        res = super(AccountInvoiceReport, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar,
            submenu=submenu)
        if view_type == 'search':
            doc = etree.XML(res['arch'])
            search_name_last_month =  False
            search_name_inuka_month =  False
            date_today = date.today().strftime('%d')
            if int(date_today) in [x for x in range(1,8)]:
                search_name_last_month = "//filter[@name='last_month']"
                search_name_inuka_month= "//filter[@name='inuka_month']"
            else:
                search_name_last_month = "//filter[@name='last_month_1_7']"
                search_name_inuka_month = "//filter[@name='inuka_month_1_7']"
            if search_name_last_month:
                nodes = doc.xpath(search_name_last_month)
                for node in nodes:
                    node.set('invisible', '1')
                    setup_modifiers(node)
            if search_name_inuka_month:
                nodes = doc.xpath(search_name_inuka_month)
                for node in nodes:
                    node.set('invisible', '1')
                    setup_modifiers(node)
            res['arch'] = etree.tostring(doc)
        return res