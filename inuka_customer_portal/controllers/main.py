import base64
import werkzeug
import odoo
import time
from odoo import http, _, tools
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager, get_records_pager
from odoo.osv.expression import OR
import pprint
import random
import string
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from random import randint
import logging
from odoo.addons.web.controllers.main import Home, ensure_db
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)


class Home(Home):
    @http.route()
    def web_login(self, redirect=None, **kw):
        ensure_db()
        request.params['login_success'] = False
        if request.httprequest.method == 'GET' and redirect and request.session.uid:
            return http.redirect_with_hash(redirect)

        if not request.uid:
            request.uid = odoo.SUPERUSER_ID

        values = request.params.copy()
        try:
            values['databases'] = http.db_list()
        except odoo.exceptions.AccessDenied:
            values['databases'] = None

        if request.httprequest.method == 'POST':
            old_uid = request.uid
            uid = request.session.authenticate(request.session.db, request.params['login'], request.params['password'])
            if uid is not False:
                request.params['login_success'] = True
                user = request.env['res.users'].sudo().browse([int(uid)])
                if user.has_group('base.group_portal'):
                    return http.redirect_with_hash('/my')
                return http.redirect_with_hash(self._login_redirect(uid, redirect=redirect))
            request.uid = old_uid
            values['error'] = _("Wrong login/password")
        else:
            if 'error' in request.params and request.params.get('error') == 'access':
                values['error'] = _('Only employee can access this database. Please contact the administrator.')

        if 'login' not in values and request.session.get('auth_login'):
            values['login'] = request.session.get('auth_login')

        if not odoo.tools.config['list_db']:
            values['disable_database_manager'] = True

        response = request.render('web.login', values)
        response.headers['X-Frame-Options'] = 'DENY'
        return response


class InukaCustomerPortal(CustomerPortal):

    @http.route(['/my', '/my/home'], type='http', auth='user', website=True)
    def dashboard(self, **kw):
        if request.context.get('uid'):
            res_funds = request.env['reserved.fund'].sudo().search(
                [('customer_id', '=', request.env.user.partner_id.id)])
            amount_reserve = sum([x.amount for x in res_funds])
            reserve = - (
                    request.env.user.partner_id.credit - request.env.user.partner_id.debit) + request.env.user.partner_id.credit_limit - amount_reserve
            values = {
                'page_display_name': 'Dashboard',
                'page_name': "dashboard",
                'partner': request.env.user.partner_id,
                'reserve': reserve
            }
            return request.render('inuka_customer_portal.dashboard', values)
        else:
            return request.redirect('/web/login')

    @http.route('/my/performance', type='http', auth='user', website=True, sitemap=False)
    def my_performance(self, **kw):
        date = datetime.now()
        current_year = date.year

        month = time.strftime('%b', time.struct_time((0, date.month, 0,) + (0,) * 6))
        quater = ''
        if month in ['Jun', 'Jul', 'Aug']:
            quater = 'q1'
        if month in ['Sep', 'Oct', 'Nov']:
            quater = 'q2'
        if month in ['Dec', 'Jan', 'Feb']:
            quater = 'q3'
        if month in ['Mar', 'Apr', 'May']:
            quater = 'q4'
        recent_history = {}
        recent_performace_history = request.env['performance.history'].sudo().search(
            [('partner_id', '=', request.env.user.partner_id.id), ('years', '=', current_year + 1),
             ('quarters', '=', quater)])
        for each in recent_performace_history:
            if each.months in recent_history:
                recent_history[each.months]['ppv'] += each.personal_pv
                recent_history[each.months]['gpv'] += each.pv_tot_group
                recent_history[each.months]['active_member'] += each.personal_members
                recent_history[each.months]['new_member'] += each.new_members
                recent_history[each.months]['pv_downline_1'] += each.pv_downline_1
                recent_history[each.months]['pv_downline_2'] += each.pv_downline_2
                recent_history[each.months]['pv_downline_3'] += each.pv_downline_3
                recent_history[each.months]['pv_downline_4'] += each.pv_downline_4
            else:
                recent_history.update({
                    each.months: {
                        'sale_month': (each.months).title(),
                        'ppv': each.personal_pv,
                        'gpv': each.pv_tot_group,
                        'active_member': each.personal_members,
                        'new_member': each.new_members,
                        'pv_downline_1': each.pv_downline_1,
                        'pv_downline_2': each.pv_downline_2,
                        'pv_downline_3': each.pv_downline_3,
                        'pv_downline_4': each.pv_downline_4,
                    }
                })
        current_date = date.date()

        last_year = datetime.strptime('07-06-%s 00:00:00' % (current_year), '%d-%m-%Y %H:%M:%S')
        next_year = datetime.strptime('06-06-%s 23:59:59' % (current_year), '%d-%m-%Y %H:%M:%S') + relativedelta(
            years=1)
        if current_date < last_year.date():
            year = current_year
        else:
            year = current_year + 1

        performace_history = request.env['performance.history'].sudo().search(
            [('partner_id', '=', request.env.user.partner_id.id), ('years', '=', year)])
        history = {
            'date': '(%s to %s)' % (last_year.date(), next_year.date()),
            'ppv': 0,
            'gpv': 0
        }

        for each in performace_history:
            history['ppv'] = history['ppv'] + each.personal_pv
            history['gpv'] = history['ppv'] + each.pv_tot_group
            if each.quarters == 'q1':
                if history.get('q1'):
                    ppv = history.get('q1').get('ppv') + each.personal_pv
                    gpv = history.get('q1').get('gpv') + each.pv_tot_group
                    active_member = history.get('q1').get('active_member') + each.personal_members
                    new_member = history.get('q1').get('new_member') + each.new_members
                else:
                    ppv = each.personal_pv
                    gpv = each.pv_tot_group
                    active_member = each.personal_members
                    new_member = each.new_members
                history['q1'] = {
                    'sales_quater': '1 (Jun-Aug)',
                    'ppv': ppv,
                    'gpv': gpv,
                    'active_member': active_member,
                    'new_member': new_member
                }
            if each.quarters == 'q2':
                if history.get('q2'):
                    ppv = history.get('q2').get('ppv') + each.personal_pv
                    gpv = history.get('q2').get('gpv') + each.pv_tot_group
                    active_member = history.get('q2').get('active_member') + each.personal_members
                    new_member = history.get('q2').get('new_member') + each.new_members
                else:
                    ppv = each.personal_pv
                    gpv = each.pv_tot_group
                    active_member = each.personal_members
                    new_member = each.new_members
                history['q2'] = {
                    'sales_quater': '1 (Sep-Nov)',
                    'ppv': ppv,
                    'gpv': gpv,
                    'active_member': active_member,
                    'new_member': new_member
                }
            if each.quarters == 'q3':
                if history.get('q3'):
                    ppv = history.get('q3').get('ppv') + each.personal_pv
                    gpv = history.get('q3').get('gpv') + each.pv_tot_group
                    active_member = history.get('q3').get('active_member') + each.personal_members
                    new_member = history.get('q3').get('new_member') + each.new_members
                else:
                    ppv = each.personal_pv
                    gpv = each.pv_tot_group
                    active_member = each.personal_members
                    new_member = each.new_members
                history['q3'] = {
                    'sales_quater': '1 (Dec-Feb)',
                    'ppv': ppv,
                    'gpv': gpv,
                    'active_member': active_member,
                    'new_member': new_member
                }
            if each.quarters == 'q4':
                if history.get('q4'):
                    ppv = history.get('q4').get('ppv') + each.personal_pv
                    gpv = history.get('q4').get('gpv') + each.pv_tot_group
                    active_member = history.get('q4').get('active_member') + each.personal_members
                    new_member = history.get('q4').get('new_member') + each.new_members
                else:
                    ppv = each.personal_pv
                    gpv = each.pv_tot_group
                    active_member = each.personal_members
                    new_member = each.new_members
                history['q4'] = {
                    'sales_quater': '1 (Mar-May)',
                    'ppv': ppv,
                    'gpv': gpv,
                    'active_member': active_member,
                    'new_member': new_member
                }

        values = {
            'page_display_name': 'Performance',
            'page_name': "performance",
            'partner': request.env.user.partner_id,
            'history': history,
            'recent_history': recent_history
        }
        return request.render('inuka_customer_portal.performance', values)

    @http.route('/my/registermember', type='http', auth='user', website=True, sitemap=False)
    def register_member(self, **kw):
        values = {
            'page_display_name': 'Register Member',
            'page_name': "register_member",
        }
        return request.render('inuka_customer_portal.member_registration_page', values)

    @http.route('/create_member', type='http', auth='user', website=True, csrf=False, method=['post'], sitemap=False)
    def create_member(self, **kw):
        mobile = str(kw.get('countryCode')).strip('+') + '' + str(kw.get('mobile'))
        partner = request.env['res.partner'].sudo().create({
            'name': str(kw.get('first_name')) + ' ' + str(kw.get('last_name')),
            'first_name': kw.get('first_name'),
            'last_name': kw.get('last_name'),
            'phone': kw.get('phone') or False,
            'mobile': mobile,
            'email': kw.get('email') or False,
            'passport_no': kw.get('passport_no') or False,
            'dob': kw.get('dob') or False,
            'street': kw.get('street') or False,
            'street2': kw.get('street2') or False,
            'city': kw.get('city') or False,
            'zip': kw.get('zip') or False,
            'state_id': int(kw.get('state_id') or 0),
            'country_id': int(kw.get('country_id') or 0),
            'kit': kw.get('kit') or False,
            'property_delivery_carrier_id': int(kw.get('property_delivery_carrier_id') or 0),
            'comment': kw.get('comment') or False,
            'join_date': datetime.today().date(),
            'upline': request.env.user.partner_id.id,
            'ref': ''.join(random.choice(string.ascii_letters).upper() for x in range(3)) + (str(randint(100, 999)))
        })

        sale_order = request.env['sale.order'].sudo().search([('partner_id', '=', partner.id)], limit=1,
                                                             order='id desc')
        if kw.get('same_address') != 'on':
            partner_shipping_address = request.env['res.partner'].sudo().create({
                'name': partner.name,
                'street': kw.get('delivery_street'),
                'street2': kw.get('delivery_street2'),
                'city': kw.get('delivery_city'),
                'zip': kw.get('delivery_zip'),
                'state_id': int(kw.get('delivery_state_id')),
                'country_id': int(kw.get('delivery_country_id')),
            })
            sale_order.sudo().write({
                'partner_shipping_id': partner_shipping_address.id,
                'carrier_id': int(kw.get('property_delivery_carrier_id')),
                'paid': True,
                'channel': 'portal'
            })
        else:
            sale_order.sudo().write({
                'partner_shipping_id': partner.id,
                'carrier_id': int(kw.get('property_delivery_carrier_id')),
                'paid': True,
                'channel': 'portal'
            })

        sale_order.get_delivery_price()
        sale_order.set_delivery_line()
        request.session['customer_portal_sale_order'] = sale_order.id
        return request.redirect('/customer/payment')

    @http.route('/customer/payment/', type='http', auth='user', website=True, sitemap=False)
    def customer_payment(self, **kw):
        order_id = request.session.get('customer_portal_sale_order')
        order = request.env['sale.order'].sudo().search([('id', '=', order_id)])
        payment_acquirer = request.env['payment.acquirer'].sudo().search([('provider', '=', 'mygate')])
        tx_values = {
            'acquirer_id': payment_acquirer.id,
            'type': 'form',
            'amount': "{0:.2f}".format(order.amount_total or 0),
            'currency_id': order.pricelist_id.currency_id.id,
            'partner_id': order.partner_id.id,
            'partner_country_id': order.partner_id.country_id.id,
            'reference': request.env['payment.transaction']._get_next_reference(order.name, acquirer=payment_acquirer),
            'sale_order_id': order.id,
        }
        tx = request.env['payment.transaction'].sudo().create(tx_values)
        values = {
            'order': order,
            'payment': payment_acquirer,
            'page_display_name': 'Register Member',
            'child_page_display_name': 'Payment',
            'page_name': "customer_payment",
            'tx': tx
        }
        return request.render('inuka_customer_portal.confirm_payment', values)

    @http.route(['/my/smslog', '/my/smslog/page/<int:page>'], type='http', auth='user', website=True,
                sitemap=False)
    def my_sms_logs(self, page=1, sortby=None, **kw):

        sms = request.env['sms.message']
        domain = [
            ('to_mobile', 'ilike', request.env.user.partner_id.mobile)
        ]

        searchbar_sortings = {
            'from_mobile': {'label': _('From Mobile'), 'order': 'from_mobile desc'},
            'message_date': {'label': _('Message Date'), 'order': 'message_date desc'},
        }

        if not sortby:
            sortby = 'message_date'
        sort_order = searchbar_sortings[sortby]['order']
        order_count = sms.sudo().search_count(domain)
        pager = portal_pager(
            url="/my/smslog",
            url_args={'sortby': sortby},
            total=order_count,
            page=page,
            step=25
        )
        sms = sms.sudo().search(domain, order=sort_order, limit=25, offset=pager['offset'])
        request.session['my_sms_log_history'] = sms.ids[:100]
        values = {
            'page_name': "SMS Logs",
            'sms_logs': sms,
            'pager': pager,
            'default_url': '/my/smslog',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'page_display_name': 'SMS Logs',
            'page_name': "sms_log",
        }
        return request.render('inuka_customer_portal.sms_log', values)

    @http.route(['/my/downloads', '/my/downloads/page/<int:page>'], type='http', auth='user', website=True,
                sitemap=False)
    def my_downloads(self, page=1, filter_id=0, **kw):
        attachments = request.env['ir.attachment']
        domain = [
            ('public', '=', True),
            ('is_portal_visible', '=', True)
        ]

        if filter_id:
            domain.append(('folder_id', '=', int(filter_id)))
        order_count = attachments.sudo().search_count(domain)
        pager = portal_pager(
            url="/my/downloads",
            url_args={},
            total=order_count,
            page=page,
            step=25
        )
        folder_data = request.env['document.folder'].sudo().search_read([], ['id', 'name'])
        attachments = attachments.sudo().search(domain, limit=25, offset=pager['offset'])
        request.session['my_downloads_history'] = attachments.ids[:100]
        values = {
            'page_name': "Download",
            'attachments': attachments,
            'pager': pager,
            'default_url': '/my/downloads',
            'page_display_name': 'Downloads',
            'page_name': "download",
            'folder_data': folder_data,
            'filter_id': filter_id
        }
        return request.render('inuka_customer_portal.download', values)

    @http.route('/my/payment', type='http', auth='user', website=True, sitemap=False)
    def my_payment(self, **kw):
        payment_acquirer = request.env['payment.acquirer'].sudo().search([('provider', '=', 'mygate')])
        values = {
            'payment': payment_acquirer,
            'page_display_name': 'Payments',
            'page_name': "payment",
        }
        return request.render('inuka_customer_portal.payment', values)

    @http.route('/my/feature', type='http', auth='user', website=True, sitemap=False)
    def my_feature(self, **kw):
        values = {
            'page_display_name': 'Suggest a Feature',
            'page_name': "feature",
        }
        return request.render('inuka_customer_portal.feature', values)

    @http.route('/create/helpdesk_ticket', type='http', auth='user', website=True, csrf=False, method=['post'],
                sitemap=False)
    def create_ticket(self, **kw):
        support_team = request.env['helpdesk.team'].sudo().search([('name', '=', 'Support')])
        ticket = request.env['helpdesk.ticket'].sudo().create({
            'name': kw.get('subject'),
            'description': kw.get('suggestion'),
            'partner_id': request.env.user.partner_id.id,
            'team_id': support_team.id
        })
        return request.redirect('/feature/sent')

    @http.route('/feature/sent', type='http', auth='user', website=True, csrf=False, method=['post'],
                sitemap=False)
    def feature_sent(self, **kw):
        values = {
            'page_display_name': 'Suggest a Feature',
            'page_name': "feature",
        }
        return request.render('inuka_customer_portal.feature_sent', values)

    @http.route(['/my/downline', '/my/downline/page/<int:page>'], type='http', auth='user', website=True, sitemap=False)
    def my_members(self, page=1, sortby=None, search=None, search_in='name', **kw):
        members = request.env['res.partner']
        domain = [
            ('upline', '=', request.env.user.partner_id.id)
        ]

        searchbar_sortings = {
            'ref': {'label': _('Member Id'), 'order': 'ref desc'},
            'name': {'label': _('Name'), 'order': 'name'},
            'status': {'label': _('Status'), 'order': 'status'},
            'join_date': {'label': _('Join Date'), 'order': 'join_date'},
        }

        searchbar_inputs = {
            'all': {'input': 'all', 'label': _('Search in All')},
            'name': {'input': 'name', 'label': _('Name')},
            'ref': {'input': 'ref', 'label': _('Member ID')},
            'status': {'input': 'status', 'label': _('Status')},
            'region': {'input': 'region', 'label': _('Region')},
        }

        if search and search_in:
            search_domain = []
            if search_in in ('name', 'all'):
                search_domain = OR([search_domain, ['|', ('name', 'ilike', search), ('display_name', 'ilike', search)]])
            if search_in in ('ref', 'all'):
                search_domain = OR([search_domain, [('ref', 'ilike', search)]])
            if search_in in ('status', 'all'):
                search_domain = OR([search_domain, [('status', 'ilike', search)]])
            if search_in in ('region', 'all'):
                search_domain = OR([search_domain, [('state_id.name', 'ilike', search)]])
            domain += search_domain

        if not sortby:
            sortby = 'join_date'
        sort_order = searchbar_sortings[sortby]['order']
        order_count = members.sudo().search_count(domain)
        pager = portal_pager(
            url="/my/downline",
            url_args={'sortby': sortby},
            total=order_count,
            page=page,
            step=25
        )
        members = members.sudo().search(domain, order=sort_order, limit=25, offset=pager['offset'])
        request.session['my_member_history'] = members.ids[:100]
        values = {
            'page_display_name': 'Downline',
            'page_name': "downline",
            'members': members,
            'pager': pager,
            'default_url': '/my/downline',
            'searchbar_sortings': searchbar_sortings,
            'searchbar_inputs': searchbar_inputs,
            'sortby': sortby,
            'search_in': search_in,
            'search': search,
        }
        return request.render('inuka_customer_portal.members_page', values)

    @http.route(['/my/downline/<int:member>'], type='http', auth="public", website=True)
    def inuka_member_detail(self, member=None, **kw):
        member = request.env['res.partner'].sudo().browse([member])
        history = request.session.get('my_member_history', [])
        idx = history.index(member.id)
        if idx != 0 and member.browse(history[idx - 1]):
            prev_record = '/my/downline/%i' % (member.browse(history[idx - 1]).id)
        else:
            prev_record = False
        if idx < len(history) - 1 and member.browse(history[idx - 1]):
            next_record = '/my/downline/%i' % (member.browse(history[idx + 1]).id)
        else:
            next_record = False
        values = {
            'member': member,
            'prev_record': prev_record,
            'next_record': next_record,
            'page_display_name': 'Downline',
            'child_page_display_name': member.name,
            'page_name': "downline",
        }
        return request.render("inuka_customer_portal.member_detail", values)

    @http.route(
        ['/customer_payment/mygate/return', '/customer_payment/mygate/cancel', '/customer_payment/mygate/error'],
        type='http',
        auth='public', csrf=False)
    def customer_payu_return(self, **post):
        """ mygate."""
        _logger.info(
            'mygate: entering form_feedback with post data %s', pprint.pformat(post))
        return_url = '/customer/payment/error'
        if post.get('_RESULT') == '0':
            return_url = '/customer/payment/confirmation'
        if post:
            request.env['payment.transaction'].sudo().form_feedback(post, 'mygate')
        request.session['mygate_post_data'] = post
        return werkzeug.utils.redirect(return_url)

    @http.route(
        ['/customer/payment/confirmation'],
        type='http',
        auth='public', csrf=False, website=True)
    def customer_payu_confirm(self, **post):
        order_id = request.session.get('customer_portal_sale_order')
        if not order_id:
            return request.redirect('/my/home')
        order = request.env['sale.order'].sudo().search([('id', '=', order_id)])
        values = {
            'order': order,
            'page_display_name': 'Register Member',
            'child_page_display_name': 'Payment',
            'page_name': "customer_payment",
        }
        request.session['customer_portal_sale_order'] = False
        return request.render('inuka_customer_portal.payment_confirmation', values)

    @http.route(
        ['/customer/payment/error'],
        type='http',
        auth='public', csrf=False, website=True)
    def customer_payu_error(self, **post):
        order_id = request.session.get('customer_portal_sale_order')
        if not order_id:
            return request.redirect('/my/home')
        order = request.env['sale.order'].sudo().search([('id', '=', order_id)])
        values = {
            'order': order,
            'post': request.session.get('mygate_post_data'),
            'page_display_name': 'Register Member',
            'child_page_display_name': 'Payment',
            'page_name': "customer_payment",
        }
        return request.render('inuka_customer_portal.payment_unsuccessful', values)

    @http.route(
        ['/mygate/return', '/mygate/cancel', '/mygate/error'],
        type='http',
        auth='public', csrf=False)
    def payment_return(self, **post):
        _logger.info(
            'mygate: entering form_feedback with post data %s', pprint.pformat(post))
        return_url = '/my/payment/error'
        request.session['mygate_post_payment_data'] = post
        if post.get('_RESULT') == '0':
            return_url = '/my/payment/confirmation'
        return werkzeug.utils.redirect(return_url)

    @http.route(
        ['/my/payment/confirmation'],
        type='http',
        auth='public', csrf=False, website=True)
    def payment_confirm(self, **post):
        post = request.session.get('mygate_post_payment_data')
        payment_acquirer = request.env['payment.acquirer'].sudo().search([('provider', '=', 'mygate')])
        tx_id = request.env['payment.transaction'].sudo().create({
            'reference': request.env['payment.transaction']._get_next_reference('post_wallet',
                                                                                acquirer=payment_acquirer),
            'acquirer_id': payment_acquirer.id,
            'amount': float(post.get('_AMOUNT')),
            'currency_id': request.website.currency_id.id,
            'partner_id': request.env.user.partner_id.id,
            'acquirer_reference': post.get('_TRANSACTIONINDEX'),
            'state': 'done'
        })
        payment = request.env['account.payment'].sudo().create({
            'payment_type': 'inbound',
            'payment_transaction_id': tx_id.id,
            'partner_id': request.env.user.partner_id.id,
            'partner_type': 'customer',
            'amount': float(post.get('_AMOUNT')),
            'journal_id': payment_acquirer.journal_id.id,
            'payment_method_id': payment_acquirer.journal_id.inbound_payment_method_ids.id
        })
        payment.post()
        values = {
            'post': post,
            'page_display_name': 'Payment',
            'page_name': "payment",
        }
        return request.render('inuka_customer_portal.payment_confirmation', values)

    @http.route(
        ['/my/payment/error'],
        type='http',
        auth='public', csrf=False, website=True)
    def payment_error(self, **post):
        post = request.session.get('mygate_post_payment_data')
        values = {
            'post': post,
            'page_display_name': 'Payment',
            'page_name': "payment",
        }
        return request.render('inuka_customer_portal.payment_unsuccessful', values)

    @http.route(['/check_unique_data'], type='json', website=True)
    def check_unique_data(self, type, data, **kw):
        res = request.env['res.partner'].sudo().search([(type, '=', data.strip('+'))])
        if res:
            return type
        else:
            return False

    @http.route(['/add_product_to_cart'], type='json', website=True)
    def add_product_to_cart(self, product_id, qty=1, **kw):
        if product_id:
            request.website.sale_get_order(force_create=1)._cart_update(
                product_id=int(product_id),
                add_qty=qty,
            )
            return True

    MANDATORY_BILLING_FIELDS = ["name", "phone", "email", "street", "city", "country_id"]
    OPTIONAL_BILLING_FIELDS = ["zipcode", "state_id", "vat", "mobile", "image"]

    def details_form_validate(self, data):
        error = dict()
        error_message = []

        # Validation
        for field_name in self.MANDATORY_BILLING_FIELDS:
            if not data.get(field_name):
                error[field_name] = 'missing'

        # email validation
        if data.get('email') and not tools.single_email_re.match(data.get('email')):
            error["email"] = 'error'
            error_message.append(_('Invalid Email! Please enter a valid email address.'))

        # vat validation
        partner = request.env["res.partner"]
        if data.get("vat") and hasattr(partner, "check_vat"):
            if data.get("country_id"):
                data["vat"] = request.env["res.partner"].fix_eu_vat_number(int(data.get("country_id")), data.get("vat"))
            partner_dummy = partner.new({
                'vat': data['vat'],
                'country_id': (int(data['country_id'])
                               if data.get('country_id') else False),
            })
            try:
                partner_dummy.check_vat()
            except ValidationError:
                error["vat"] = 'error'

        # error message for empty required fields
        if [err for err in error.values() if err == 'missing']:
            error_message.append(_('Some required fields are empty.'))

        unknown = [k for k in data if k not in self.MANDATORY_BILLING_FIELDS + self.OPTIONAL_BILLING_FIELDS]
        if unknown:
            error['common'] = 'Unknown field'
            error_message.append("Unknown field '%s'" % ','.join(unknown))

        return error, error_message

    @http.route(['/my/account'], type='http', auth='user', website=True)
    def account(self, redirect=None, **post):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        values.update({
            'error': {},
            'error_message': [],
        })

        if post:
            error, error_message = self.details_form_validate(post)
            values.update({'error': error, 'error_message': error_message})
            values.update(post)
            if not error:
                values = {key: post[key] for key in self.MANDATORY_BILLING_FIELDS}
                values.update({key: post[key] for key in self.OPTIONAL_BILLING_FIELDS if key in post})
                if post.get('image'):
                    request.env.user.partner_id.write({
                        'image': base64.encodestring(post.get('image').read()) or False
                    })
                values.update({'zip': values.pop('zipcode', '')})
                description = "The following customer information was changed on the portal and needs your attention: \n" + str(
                    values)
                team_id = request.env['helpdesk.team'].sudo().search([('name', 'ilike', 'Data Team')], limit=1)
                ticket_type_id = request.env['helpdesk.ticket.type'].sudo().search([('name', 'ilike', 'Misc')], limit=1)
                ticket = request.env['helpdesk.ticket'].sudo().create({
                    'name': "Customer Data Change : " + values.get('name'),
                    'team_id': team_id.id,
                    'partner_id': request.env.user.partner_id.id,
                    'ticket_type_id': ticket_type_id.id,
                    'description': description
                })
                # partner.sudo().write(values)
                if redirect:
                    return request.redirect(redirect)
                return request.redirect('/my/home')

        countries = request.env['res.country'].sudo().search([])
        states = request.env['res.country.state'].sudo().search([])

        values.update({
            'partner': partner,
            'countries': countries,
            'states': states,
            'has_check_vat': hasattr(request.env['res.partner'], 'check_vat'),
            'redirect': redirect,
            'page_display_name': 'Profile',
            'page_name': "profile",
        })

        response = request.render("portal.portal_my_details", values)
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    @http.route(['/my/orders', '/my/orders/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_orders(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        res = super(InukaCustomerPortal, self).portal_my_orders(page, date_begin, date_end, sortby, **kw)
        res.qcontext['page_name'] = 'sale_order'
        res.qcontext['page_display_name'] = 'Orders'
        return res

    @http.route(['/my/orders/<int:order>', ], type='http', auth="public", website=True)
    def portal_order_page(self, order=None, access_token=None, **kw):
        res = super(InukaCustomerPortal, self).portal_order_page(order, access_token, **kw)
        res.qcontext['page_name'] = 'sale_order'
        res.qcontext['page_display_name'] = 'Orders'
        res.qcontext['child_page_display_name'] = res.qcontext['order'].name
        return res

    @http.route(['/my/invoices', '/my/invoices/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_invoices(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        res = super(InukaCustomerPortal, self).portal_my_invoices(page, date_begin, date_end, sortby, **kw)
        res.qcontext['page_name'] = 'invoice'
        res.qcontext['page_display_name'] = 'Invoices'
        return res

    @http.route(['/my/invoices/<int:invoice_id>'], type='http', auth="public", website=True)
    def portal_my_invoice_detail(self, invoice_id, access_token=None, **kw):
        res = super(InukaCustomerPortal, self).portal_my_invoice_detail(invoice_id, access_token, **kw)
        res.qcontext['page_name'] = 'invoice'
        res.qcontext['page_display_name'] = 'Invoices'
        res.qcontext['child_page_display_name'] = res.qcontext['invoice'].number
        return res

    @http.route(['/my/tickets', '/my/tickets/page/<int:page>'], type='http', auth="user", website=True)
    def my_helpdesk_tickets(self, page=1, date_begin=None, date_end=None, sortby=None, search=None, search_in='content',
                            **kw):
        res = super(InukaCustomerPortal, self).my_helpdesk_tickets(page, date_begin, date_end, sortby, search,
                                                                   search_in, **kw)
        res.qcontext['page_name'] = 'ticket'
        res.qcontext['page_display_name'] = 'Tickets'
        return res

    @http.route([
        "/helpdesk/ticket/<int:ticket_id>",
        "/helpdesk/ticket/<int:ticket_id>/<token>"
    ], type='http', auth="public", website=True)
    def tickets_followup(self, ticket_id, token=None):
        res = super(InukaCustomerPortal, self).tickets_followup(ticket_id, token)
        res.qcontext['page_name'] = 'ticket'
        res.qcontext['page_display_name'] = 'Tickets'
        res.qcontext['child_page_display_name'] = res.qcontext['ticket'].id
        return res


class WebsiteSale(WebsiteSale):
    @http.route(type='http', auth="user", website=True)
    def shop(self, page=0, category=None, search='', ppg=False, **post):
        return super(WebsiteSale, self).shop(page, category, search, ppg, **post)

    @http.route(['/shop/cart/update'], type='http', auth="public", methods=['POST'], website=True, csrf=False)
    def cart_update(self, product_id, add_qty=1, set_qty=0, **kw):
        request.website.sale_get_order(force_create=1)._cart_update(
            product_id=int(product_id),
            add_qty=add_qty,
            set_qty=set_qty,
            attributes=self._filter_attributes(**kw),
        )
        if kw.get('from_shop'):
            return request.redirect("/shop")
        else:
            return request.redirect("/shop/cart")
