# -*- coding: utf-8 -*-
from odoo import http

# class OdooOffice265(http.Controller):
#     @http.route('/odoo_office265/odoo_office265/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/odoo_office265/odoo_office265/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('odoo_office265.listing', {
#             'root': '/odoo_office265/odoo_office265',
#             'objects': http.request.env['odoo_office265.odoo_office265'].search([]),
#         })

#     @http.route('/odoo_office265/odoo_office265/objects/<model("odoo_office265.odoo_office265"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('odoo_office265.object', {
#             'object': obj
#         })