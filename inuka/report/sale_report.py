# -*- coding:utf-8 -*-

from odoo import fields, models, api
from lxml import etree
from odoo.osv.orm import setup_modifiers
from datetime import datetime, date


class SaleReport(models.Model):
    _inherit = "sale.report"

    pv = fields.Float("PV's", readonly=True)
    sale_date = fields.Date(string="Sale Date", readonly=True)
    amount_total = fields.Float(string="Total Including Tax", readonly=True,)

    def _select(self):
        select_str = super(SaleReport, self)._select()
        select_str += """ ,l.pv as pv
                          ,s.sale_date as sale_date
                          ,sum(l.price_total / COALESCE(cr.rate, 1.0)) as amount_total"""
        return select_str

    def _group_by(self):
        group_by_str = super(SaleReport,self)._group_by()
        group_by_str += """,l.pv 
                           ,s.sale_date
                           ,s.amount_total"""
        return group_by_str

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False,
                        submenu=False):
        res = super(SaleReport, self).fields_view_get(
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
