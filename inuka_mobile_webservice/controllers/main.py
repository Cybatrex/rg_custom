import threading

from odoo import http
from odoo.http import request
import inspect
from xmlrpc import client
import re


class WebService(http.Controller):
    @http.route(['/mobilewstest'], type='http', auth='user', website=True)
    def mobilewstest(self, **kw):
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        value = {}
        if kw:
            db = threading.current_thread().dbname
            unm = "leereddy05@gmail.comxx"
            pwd = "thisTime@2018!!"
            common_proxy = client.ServerProxy('%s/xmlrpc/common' % (base_url))
            object_proxy = client.ServerProxy('%s/xmlrpc/object' % (base_url))
            uid = common_proxy.login(db, unm, pwd)
            service = kw.pop('service')
            response = object_proxy.execute(db, uid, pwd, "inuka.web.service", service, kw)
            value['response'] = response
        return request.render('inuka_mobile_webservice.mobilewstest_template', value)

    @http.route(['/get_require_parameters'], type='json', auth='user', website=True)
    def get_require_parameters(self, service, **kw):
        service_obj = request.env['inuka.web.service'].sudo()
        if hasattr(service_obj, service):
            tx = getattr(service_obj, service)
            docs = tx.__doc__.splitlines()
            param_list = []
            for each in docs:
                if each:
                    data = re.sub(r"\s", "", each).split('=')
                    if len(data) >= 2:
                        param_list.append({
                            'param': data[0],
                            'require': data[1]
                        })

            return param_list
