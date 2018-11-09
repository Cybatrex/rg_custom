# -*- coding: utf-8 -*-
from odoo import http

# class InukaPos(http.Controller):
#     @http.route('/inuka_pos/inuka_pos/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/inuka_pos/inuka_pos/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('inuka_pos.listing', {
#             'root': '/inuka_pos/inuka_pos',
#             'objects': http.request.env['inuka_pos.inuka_pos'].search([]),
#         })

#     @http.route('/inuka_pos/inuka_pos/objects/<model("inuka_pos.inuka_pos"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('inuka_pos.object', {
#             'object': obj
#         })