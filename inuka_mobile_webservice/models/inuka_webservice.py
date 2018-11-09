from odoo import fields, api, models, _
from datetime import datetime
import json
import base64
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager, get_records_pager


class FavouriteMembers(models.Model):
    _name = 'favourite.members'

    partner_id = fields.Many2one('res.partner', string="Partner")
    fav_member_id = fields.Many2one('res.partner', string="Member")


class InukaWebService(models.Model):
    _name = 'inuka.web.service'

    @api.model
    def add_to_favourite(self, kw):
        '''
            product_id = required
            user_id = required
        '''
        product_id = kw.get('product_id')
        user_id = kw.get('user_id')
        if not product_id:
            return json.dumps({'status': False, 'message': _('Please provide product id.')})
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        product_id = self.env['product.product'].sudo().search(
            [('id', '=', int(product_id)), ('active', 'in', [True, False])])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        if not product_id:
            return json.dumps({'status': False, 'message': _('Product not available in system.')})
        wishlist_id = self.env['product.wishlist'].sudo().search(
            [('product_id', '=', product_id.id), ('partner_id', '=', user_id.partner_id.id)])
        website_id = self.env.ref('website.default_website')
        if wishlist_id:
            return json.dumps({'status': False, 'message': _('Product is already in favourite.')})
        else:
            try:
                self.env['product.wishlist'].sudo().create({
                    'partner_id': user_id.partner_id.id,
                    'product_id': product_id.id,
                    'website_id': website_id.id,
                    'pricelist_id': user_id.partner_id.property_product_pricelist.id,
                    'price': product_id.lst_price
                })
                return json.dumps({'status': True, 'message': _('Added in favourite.')})
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def add_to_cart(self, kw):
        '''
            product_id = required
            user_id = required
            cart_id = optional
            qty = optional
        '''
        product_id = kw.get('product_id')
        user_id = kw.get('user_id')
        cart_id = kw.get('cart_id')
        qty = kw.get('qty')
        if not product_id:
            return json.dumps({'status': False, 'message': _('Please provide product id.')})
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        product_id = self.env['product.product'].sudo().search([('id', '=', int(product_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        if not product_id:
            return json.dumps({'status': False, 'message': _('Product not available in system.')})
        if cart_id:
            order_line_id = self.env['sale.order.line'].sudo().search(
                [('product_id', '=', product_id.id), ('order_id', '=', int(cart_id))])
            if order_line_id:
                order_line_id.write({
                    'product_uom_qty': float(order_line_id.product_uom_qty) + float(qty)
                })
                return json.dumps({'status': False, 'message': _('Product Added in your cart.')})
            else:
                try:
                    self.env['sale.order.line'].sudo().create({
                        'order_id': int(cart_id),
                        'product_id': product_id.id,
                        'product_uom_qty': qty or 1
                    })
                    return json.dumps({'cart_id': cart_id, 'status': True, 'message': _('Product added in your cart.')})
                except Exception as e:
                    return json.dumps({'status': False, 'message': _(e)})
        else:
            team = self.env['crm.team'].sudo().search([('team_type', '=', 'website')])

            cart_id = self.env['sale.order'].sudo().create({
                'partner_id': user_id.partner_id.id,
                'team_id': team.id if team else False
            })
            self.env['sale.order.line'].sudo().create({
                'order_id': cart_id.id,
                'product_id': product_id.id,
                'product_uom_qty': qty or 1
            })
            return json.dumps({'cart_id': cart_id.id, 'status': True, 'message': _('Product added in your cart.')})

    @api.model
    def update_cart_qty(self, kw):
        '''
            product_id = required
            user_id = required
            cart_id = optional
            qty = optional
        '''
        product_id = kw.get('product_id')
        user_id = kw.get('user_id')
        cart_id = kw.get('cart_id')
        qty = kw.get('qty')
        if not product_id:
            return json.dumps({'status': False, 'message': _('Please provide product id.')})
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        product_id = self.env['product.product'].sudo().search([('id', '=', int(product_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        if not product_id:
            return json.dumps({'status': False, 'message': _('Product not available in system.')})
        if cart_id:
            order_line_id = self.env['sale.order.line'].sudo().search(
                [('product_id', '=', product_id.id), ('order_id', '=', int(cart_id))])

            if order_line_id:
                order_line_id.sudo().write({
                    'product_uom_qty': qty or 1
                })
                return json.dumps({'cart_id': cart_id, 'status': True, 'message': _('Quantity Updated.')})
            else:
                try:
                    self.env['sale.order.line'].sudo().create({
                        'order_id': int(cart_id),
                        'product_id': product_id.id,
                        'product_uom_qty': qty or 1
                    })
                    return json.dumps({'cart_id': cart_id, 'status': True, 'message': _('Product added in your cart.')})
                except Exception as e:
                    return json.dumps({'status': False, 'message': _(e)})
        else:
            team = self.env['crm.team'].sudo().search([('team_type', '=', 'website')])

            cart_id = self.env['sale.order'].sudo().create({
                'partner_id': user_id.partner_id.id,
                'team_id': team.id if team else False
            })
            self.env['sale.order.line'].sudo().create({
                'order_id': cart_id.id,
                'product_id': product_id.id,
                'product_uom_qty': qty or 1
            })
            return json.dumps({'cart_id': cart_id.id, 'status': True, 'message': _('Product added in your cart.')})

    @api.model
    def get_all_favourite_products(self, kw):
        '''
            user_id = required
        '''
        user_id = kw.get('user_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        wishlist_ids = self.env['product.wishlist'].sudo().search([('partner_id', '=', user_id.partner_id.id)],
                                                                  order='id desc')
        if not wishlist_ids:
            return json.dumps({'status': False, 'message': _('Products not available in favourite.')})
        else:
            try:
                product_list = []
                for wishlist in wishlist_ids:
                    product_list.append({
                        'id': wishlist.product_id.id,
                        'image': wishlist.product_id.image or '',
                        'name': wishlist.product_id.display_name,
                        'price': wishlist.product_id.lst_price,
                        'PV': wishlist.product_id.pv,
                    })
                return {'status': True, 'message': _(str(len(wishlist_ids)) + ' Products available in favourite.'),
                        'products': product_list}
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def get_all_products(self, kw):
        '''
            user_id = required
            category_id = required
            page = optional
            limit = optional
            order = optional
        '''
        user_id = kw.get('user_id')
        category_id = kw.get('category_id')
        limit = kw.get('limit')
        page = kw.get('page')
        order = kw.get('order')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        domain = []
        if category_id:
            domain.append(('public_categ_ids', 'in', int(category_id)))
        product_count = self.env['product.template'].sudo().search_count(domain)
        pager = portal_pager(
            url="/shop",
            total=product_count,
            page=int(page),
            step=int(limit)
        )
        product_ids = self.env['product.template'].sudo().search_read(domain, limit=int(limit),
                                                                      offset=pager['offset'], order=order)
        if not product_ids:
            return json.dumps({'status': False, 'message': _('Products not available.')})
        else:
            try:
                for product in product_ids:
                    order_id = self.env['sale.order'].sudo().search(
                        [('partner_id', '=', user_id.partner_id.id), ('team_id.team_type', '=', 'website'),
                         ('state', '=', 'draft')],
                        order='id desc', limit=1)
                    if order_id:
                        sale_order_line = self.env['sale.order.line'].sudo().search(
                            [('order_id', '=', order_id.id), ('product_id', '=', int(product.get('id')))])

                        if sale_order_line:
                            product.update({'cart_item': True})
                        else:
                            product.update({'cart_item': False})
                    wishlist_line = self.env['product.wishlist'].sudo().search(
                        [('partner_id', '=', user_id.partner_id.id), ('product_id', '=', int(product.get('id')))])
                    if wishlist_line:
                        product.update({'favourite_product': True})
                    else:
                        product.update({'favourite_product': False})
                return {'status': True, 'message': _(str(len(product_ids)) + ' Products available.'),
                        'products': product_ids}
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def get_product_details(self, kw):
        '''
                    product_id = required
                    user_id = required
                '''
        product_id = kw.get('product_id')
        user_id = kw.get('user_id')
        if not product_id:
            return json.dumps({'status': False, 'message': _('Please provide product id.')})
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        product_id = self.env['product.product'].sudo().search([('id', '=', int(product_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        if not product_id:
            return json.dumps({'status': False, 'message': _('Product not available in system.')})
        else:
            try:
                images = self.env['product.image'].sudo().search(
                    [('product_tmpl_id', '=', product_id.product_tmpl_id.id)])
                image_list = [image.image or '' for image in images]
                product = product_id.read()
                keys = product[0].keys()
                for each in keys:
                    if product[0][each] in [False, [], '']:
                        product[0][each] = ''
                wishlist_line = self.env['product.wishlist'].sudo().search(
                    [('partner_id', '=', user_id.partner_id.id), ('product_id', '=', product_id.id)])
                if wishlist_line:
                    product[0].update({'favourite_product': True})
                else:
                    product[0].update({'favourite_product': False})
                pricelist = []

                for item in product_id.item_ids:
                    pricelist.append({
                        'name': item.name,
                        'fixed_price': item.fixed_price,
                        'min_qty': item.min_quantity,
                        'start_date': item.date_start,
                        'end_date': item.date_end
                    })
                product[0].update(
                    {'images': image_list, 'status': True, 'message': _('Product Details.'), 'pricelist': pricelist})
                return product
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def get_cart_details(self, kw):
        '''
                    user_id = required
                    cart_id = optional
                '''
        user_id = kw.get('user_id')
        cart_id = kw.get('cart_id')
        if not cart_id:
            return json.dumps({'status': False, 'message': _('Please provide cart id.')})
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        order_id = self.env['sale.order'].sudo().search([('id', '=', int(cart_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        if not order_id:
            return json.dumps({'status': False, 'message': _('Cart Id not available in system.')})
        else:
            try:
                if not order_id.order_line:
                    return json.dumps({'status': False, 'message': _('No product in your cart.')})
                else:
                    product_list = [{'product_id': line.product_id.id, 'product_name': line.product_id.display_name,
                                     'product_code': line.product_id.default_code, 'personalPV': line.product_id.pv,
                                     'productPrice': line.product_id.lst_price, 'productQuantity': line.product_uom_qty,
                                     'productThumbnailImage': line.product_id.image or ''} for
                                    line in order_id.order_line]
                    return {'status': True, 'message': _(str(len(order_id.order_line)) + 'Products in your cart.'),
                            'cart_id': order_id.id, 'totalPV': order_id.total_pv, 'products': product_list,
                            'amount_untaxed': order_id.amount_untaxed,
                            'amount_tax': order_id.amount_tax,
                            'amount_total': order_id.amount_total}
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def remove_cart_item(self, kw):
        '''
                    product_id = required
                    user_id = required
                    cart_id = optional
                '''
        product_id = kw.get('product_id')
        user_id = kw.get('user_id')
        cart_id = kw.get('cart_id')
        if not cart_id:
            return json.dumps({'status': False, 'message': _('Please provide cart id.')})
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        if not product_id:
            return json.dumps({'status': False, 'message': _('Please provide product id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        order_id = self.env['sale.order'].sudo().search([('id', '=', int(cart_id))])
        product_id = self.env['product.product'].sudo().search([('id', '=', int(product_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        if not order_id:
            return json.dumps({'status': False, 'message': _('Cart Id not available in system.')})
        if not product_id:
            return json.dumps({'status': False, 'message': _('Product not available in system.')})
        else:
            try:
                order_line = self.env['sale.order.line'].sudo().search(
                    [('order_id', '=', order_id.id), ('product_id', '=', product_id.id)]).unlink()
                return json.dumps(
                    {'status': True, 'message': _('Product successfully remove from your cart')})
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def remove_wishlist_item(self, kw):
        '''
                    product_id = required
                    user_id = required
                '''
        product_id = kw.get('product_id')
        user_id = kw.get('user_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        if not product_id:
            return json.dumps({'status': False, 'message': _('Please provide product id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        product_id = self.env['product.product'].sudo().search([('id', '=', int(product_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        if not product_id:
            return json.dumps({'status': False, 'message': _('Product not available in system.')})
        else:
            try:
                wishlist_line = self.env['product.wishlist'].sudo().search(
                    [('partner_id', '=', user_id.partner_id.id), ('product_id', '=', product_id.id)])
                if wishlist_line:
                    wishlist_line.unlink()
                    return json.dumps(
                        {'status': True, 'message': _('Product successfully remove from your favourite')})
                else:
                    return json.dumps(
                        {'status': True, 'message': _('Product is not available in your favourite')})
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def get_user_address_details(self, kw):
        '''
                    user_id = required
                '''
        user_id = kw.get('user_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        else:
            try:
                billing_address = {
                    'name': user_id.partner_id.name,
                    'street': user_id.partner_id.street,
                    'street2': user_id.partner_id.street2,
                    'city': user_id.partner_id.city,
                    'state': user_id.partner_id.state_id.name,
                    'country': user_id.partner_id.country_id.name,
                    'zip': user_id.partner_id.zip,
                    'address_id': user_id.partner_id.id,
                    'email': user_id.partner_id.email or '',
                    'mobile': user_id.partner_id.mobile or ''
                }
                shipping_address_list = []
                shipping_address_details = self.env['res.partner'].sudo().search(
                    [('type', '=', 'delivery'), ('parent_id', '=', user_id.partner_id.id)])
                if not shipping_address_details:
                    shipping_address_list.append(billing_address)
                else:
                    for shipping_address in shipping_address_details:
                        shipping_address_list.append({
                            'name': shipping_address.name,
                            'street': shipping_address.street,
                            'street2': shipping_address.street2,
                            'city': shipping_address.city,
                            'state': shipping_address.state_id.name,
                            'country': shipping_address.country_id.name,
                            'zip': shipping_address.zip,
                            'address_id': shipping_address.id,
                            'email': shipping_address.email or '',
                            'mobile': shipping_address.mobile or ''
                        })
                return json.dumps({'status': True, 'message': _('Address Found.'), 'billing_address': billing_address,
                                   'shipping_addresses': shipping_address_list})
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def get_user_details(self, kw):
        '''
                    user_id = required
                '''
        user_id = kw.get('user_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        else:
            return {'status': True, 'message': _('User Found.'), 'name': user_id.name,
                    'profile_image': user_id.image or '',
                    'email': user_id.partner_id.email, 'contact_no': user_id.partner_id.phone,
                    'inuka_id': user_id.partner_id.ref,
                    'join_date': user_id.partner_id.join_date}

    @api.model
    def update_user_details(self, kw):
        '''
                    user_id = required
                    name = optional
                    image = optional
                    email = optional
                    phone = optional
                    join_date = optional
                    inuka_id = optional
                '''
        user_id = kw.get('user_id')
        name = kw.get('name')
        image = kw.get('image')
        email = kw.get('email')
        phone = kw.get('phone')
        join_date = kw.get('join_date')
        inuka_id = kw.get('inuka_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        else:
            try:
                if image:
                    image_1 = image
                else:
                    image_1 = user_id.partner_id.image or ''
                if join_date:
                    date = datetime.strptime(join_date, '%m/%d/%Y').strftime('%Y-%m-%d')
                else:
                    date = user_id.partner_id.join_date
                if image_1:
                    user_id.partner_id.sudo().write({
                        'image': image_1
                    })
                description = "The following customer information was changed on the portal and needs your attention: \n" + str(
                    {'user_id': user_id.id, 'name': name,
                     'email': email,
                     'phone': phone,
                     'join_date': date,
                     'inuka_id': inuka_id})
                team_id = self.env['helpdesk.team'].sudo().search([('name', 'ilike', 'Data Team')], limit=1)
                ticket_type_id = self.env['helpdesk.ticket.type'].sudo().search([('name', 'ilike', 'Misc')], limit=1)
                ticket = self.env['helpdesk.ticket'].sudo().create({
                    'name': "Customer Data Change : " + user_id.name,
                    'team_id': team_id.id,
                    'partner_id': user_id.partner_id.id,
                    'ticket_type_id': ticket_type_id.id,
                    'description': description
                })
                return json.dumps({'status': True, 'message': _('Profile update request has successfully received.'),
                                   'ticket_no': ticket.id})
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def add_edit_address(self, kw):
        '''
                            user_id = required
                            type = required
                            address_id = optional
                            name = optional
                            street = optional
                            street2 = optional
                            city = optional
                            state = optional
                            country = optional
                            zip = optional
                            email = optional
                            mobile = optional
                        '''
        user_id = kw.get('user_id')
        type = kw.get('type')
        address_id = kw.get('address_id')
        name = kw.get('name')
        street = kw.get('street')
        street2 = kw.get('street2')
        city = kw.get('city')
        state = kw.get('state')
        country = kw.get('country')
        zip = kw.get('zip')
        mobile = kw.get('mobile')
        email = kw.get('email')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})

        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        if not type:
            return json.dumps({'status': False, 'message': _('Please provide Type.')})
        try:
            state_id = self.env['res.country.state'].sudo().search([('id', '=', int(state))])
            country_id = self.env['res.country'].sudo().search([('id', '=', int(country))])
            vals = {
                'name': name or '',
                'street': street or '',
                'street2': street2 or '',
                'city': city or '',
                'state': state_id.id or False,
                'country': country_id.id or False,
                'zip': zip or '',
                'type': type,
                'mobile': mobile,
                'email': email
            }
            if not address_id and type == 'delivery':
                vals.update({'parent_id': user_id.partner_id.id})
                self.env['res.partner'].sudo().create(vals)
            elif not address_id and type == 'invoice':
                vals.update({'parent_id': user_id.partner_id.id})
                self.env['res.partner'].sudo().create(vals)
            elif address_id:
                address_id = self.env['res.partner'].browse([int(address_id)])
                address_id.write(vals)
            else:
                user_id.partner_id.write(vals)
            return json.dumps({'status': True, 'message': _('Address Updated.')})

        except Exception as e:
            return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def get_inuka_wallet_balance(self, kw):
        '''
            user_id = required
        '''
        user_id = kw.get('user_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        else:
            try:
                wallet_id = user_id.partner_id.property_account_receivable_id.id
                wallet_amount = user_id.partner_id.credit
                return json.dumps({'status': True, 'message': _('Wallet Balance.'), 'wallet_id': wallet_id,
                                   'wallet_amount': abs(wallet_amount)})
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def get_all_favourite_members(self, kw):
        '''
            user_id = required
        '''
        user_id = kw.get('user_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        member_ids = self.env['favourite.members'].sudo().search(
            [('partner_id', '=', user_id.partner_id.id)])
        if not member_ids:
            return json.dumps({'status': False, 'message': _('Members not available in favourite.')})
        else:
            try:
                member_list = []
                for member in member_ids:
                    member_list.append({
                        'id': member.id,
                        'image': member.image or '',
                        'name': member.name,
                        'join_date': member.join_date,
                        'active_members': member.personal_members,
                        'recruits': member.new_members,
                        'merchant_id': member.upline.id
                    })
                return {'status': True, 'message': _(str(len(member_ids)) + ' Members available in favourite.'),
                        'members': member_list}
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def get_ppv(self, kw):
        '''
            user_id = required
        '''
        user_id = kw.get('user_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        else:
            try:
                return json.dumps(
                    {'status': True, 'message': _('Personal PV.'),
                     'PPV': user_id.partner_id.personal_pv})
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def get_gpv(self, kw):
        '''
                    user_id = required
                '''
        user_id = kw.get('user_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        else:
            try:
                return json.dumps(
                    {'status': True, 'message': _('Personal GPV.'),
                     'GPV': user_id.partner_id.pv_tot_group})
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def get_dashboard_details(self, kw):
        '''
                    user_id = required
                '''
        user_id = kw.get('user_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        else:
            try:
                return json.dumps(
                    {'status': True, 'message': _('Dashboard Details.'),
                     'GPV': user_id.partner_id.pv_tot_group,
                     'PPV': user_id.partner_id.personal_pv,
                     'wallet_amount': abs(user_id.partner_id.credit)})
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def get_performance_details(self, kw):
        '''
            user_id = required
        '''
        user_id = kw.get('user_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        else:
            try:
                return json.dumps(
                    {'status': True, 'message': _('Dashboard Details.'),
                     'GPV': user_id.partner_id.pv_tot_group,
                     'PPV': user_id.partner_id.personal_pv,
                     'downline_1': user_id.partner_id.pv_downline_1,
                     'downline_2': user_id.partner_id.pv_downline_2,
                     'downline_3': user_id.partner_id.pv_downline_3,
                     'downline_4': user_id.partner_id.pv_downline_4,
                     'active_members': user_id.partner_id.personal_members,
                     'new_recruits': user_id.partner_id.new_members})
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def get_member_details(self, kw):
        '''
                    user_id = required
                '''
        user_id = kw.get('user_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        else:
            try:
                member_ids = self.env['res.partner'].sudo().search(
                    [('upline', '=', user_id.partner_id.id)])
                if not member_ids:
                    return json.dumps({'status': False, 'message': _('0 Members available.')})
                member_list = []
                for member in member_ids:
                    member_list.append({
                        'id': member.id,
                        'member_id': member.ref,
                        'name': member.display_name,
                        'status': member.status,
                        'join_date': member.join_date,
                        'region': member.state_id.name,
                        'personal_pv': member.personal_pv,
                        'group_pv': member.pv_tot_group,
                        'is_active_mtd': member.is_active_mtd,
                        'personal_members': member.personal_members,
                        'vr_earner': member.vr_earner,
                        'new_members': member.new_members,
                        'image': member.image or ''
                    })
                return {'status': True, 'message': _(str(len(member_ids)) + ' Members available in favourite.'),
                        'members': member_list}
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def get_order_details(self, kw):
        '''
                    user_id = required
                    cart_id = required
                '''
        user_id = kw.get('user_id')
        cart_id = kw.get('cart_id')
        if not cart_id:
            return json.dumps({'status': False, 'message': _('Please provide cart id.')})
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        order_id = self.env['sale.order'].sudo().search([('id', '=', int(cart_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        if not order_id:
            return json.dumps({'status': False, 'message': _('Cart Id not available in system.')})
        else:
            try:
                if not order_id.order_line:
                    return json.dumps({'status': False, 'message': _('No product in your cart.')})
                else:
                    values = {
                        'confirmation_date': order_id.confirmation_date,
                        'date_order': order_id.date_order,
                        'delivery_status': order_id.delivery_status,
                        'order_status': order_id.order_status,
                        'paid': order_id.paid,
                        'order_id': order_id.id,
                        'customer': order_id.partner_id.name,
                        'status': True,
                        'products': [
                            {'product_id': line.product_id.id, 'product_name': line.product_id.display_name,
                             'product_code': line.product_id.default_code, 'personalPV': line.product_id.pv,
                             'productPrice': line.product_id.lst_price, 'productQuantity': line.product_uom_qty,
                             'productThumbnailImage': line.product_id.image or ''} for
                            line in order_id.order_line],
                        'message': _(str(len(order_id.order_line)) + ' Products available in Order.')
                    }
                    return values
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def get_all_order_details(self, kw):
        '''
                    user_id = required
                '''
        user_id = kw.get('user_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        order_ids = self.env['sale.order'].sudo().search([('partner_id', '=', user_id.partner_id.id)])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        if not order_ids:
            return json.dumps({'status': False, 'message': _('No Orders available in system.')})
        else:
            try:
                order_list = []
                for each in order_ids:
                    order_list.append({
                        'confirmation_date': each.confirmation_date,
                        'date_order': each.date_order,
                        'delivery_status': each.delivery_status,
                        'order_status': each.order_status,
                        'paid': each.paid,
                        'order_id': each.id,
                        'customer': each.partner_id.name,
                        'status': True,
                        'products': [
                            {'product_id': line.product_id.id, 'product_name': line.product_id.display_name,
                             'product_code': line.product_id.default_code, 'personalPV': line.product_id.pv,
                             'productPrice': line.product_id.lst_price, 'productQuantity': line.product_uom_qty,
                             'productThumbnailImage': line.product_id.image or ''} for
                            line in each.order_line],
                        'message': _(str(len(each.order_line)) + ' Products available in Order.')
                    })
                    return order_list
            except Exception as e:
                return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def submit_contact_us_details(self, kw):
        '''
            user_id = required
            name = optional
            contact_no = optional
            email = optional
            subject = optional
            message = optional
            suggest_feature = optional
        '''
        user_id = kw.get('user_id')
        name = kw.get('name')
        contact_no = kw.get('contact_no')
        email = kw.get('email')
        subject = kw.get('subject')
        message = kw.get('message')
        suggest_feature = kw.get('suggest_feature')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        if not email:
            return json.dumps({'status': False, 'message': _('Please provide email address')})
        if not subject:
            return json.dumps({'status': False, 'message': _('Please provide subject')})
        if not message:
            return json.dumps({'status': False, 'message': _('Please provide message')})
        if not name:
            return json.dumps({'status': False, 'message': _('Please provide name')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        try:
            self.env['crm.lead'].sudo().create({
                'name': subject,
                'partner_id': user_id.partner_id.id,
                'contact_name': name,
                'email_from': email,
                'phone': contact_no or False,
                'description': message
            })
            return json.dumps({'status': True, 'message': _('Your message has been sent successfully.')})
        except Exception as e:
            return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def add_money_to_wallet(self, kw):
        '''
            user_id = required
            payment_amount = required
            reference = required
        '''
        user_id = kw.get('user_id')
        payment_amount = kw.get('payment_amount')
        reference = kw.get('reference')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        if not payment_amount:
            return json.dumps({'status': False, 'message': _('Please provide payment amount')})
        if not reference:
            return json.dumps({'status': False, 'message': _('Please provide reference.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        try:
            payment_acquirer = self.env['payment.acquirer'].sudo().search([('provider', '=', 'mygate')])
            tx_id = self.env['payment.transaction'].sudo().create({
                'reference': self.env['payment.transaction']._get_next_reference('post_wallet',
                                                                                 acquirer=payment_acquirer),
                'acquirer_id': payment_acquirer.id,
                'amount': float(payment_amount),
                'currency_id': user_id.company_id.currency_id.id,
                'partner_id': user_id.partner_id.id,
                'acquirer_reference': reference,
                'state': 'done'
            })
            payment = self.env['account.payment'].sudo().create({
                'payment_type': 'inbound',
                'payment_transaction_id': tx_id.id,
                'partner_id': user_id.partner_id.id,
                'partner_type': 'customer',
                'amount': int(payment_amount),
                'journal_id': payment_acquirer.journal_id.id,
                'payment_method_id': payment_acquirer.journal_id.inbound_payment_method_ids.id
            })
            payment.post()
            wallet_id = user_id.partner_id.property_account_receivable_id.id
            wallet_amount = user_id.partner_id.credit
            return json.dumps(
                {'status': True, 'message': _('Amount added in your wallet.'), 'transaction_id': wallet_id,
                 'reference': tx_id.reference,
                 'wallet_amount': abs(wallet_amount)})
        except Exception as e:
            return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def get_account_history(self, kw):
        '''
            user_id = required
            wallet_id = optional

        '''
        user_id = kw.get('user_id')
        wallet_id = kw.get('wallet_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        domain = [('partner_id', '=', user_id.partner_id.id)]
        if wallet_id:
            domain.append(('account_id', '=', int(wallet_id)))
        try:
            account = self.env['account.move.line'].sudo().search(domain)
            transaction_list = []
            for each in account:
                transaction_list.append({
                    'transaction_id': each.account_id.id,
                    'transaction_name': each.name,
                    'transaction_details': 'credit' if each.credit else 'debit',
                    'transaction_date': each.date,
                    'transaction_amount': each.credit if each.credit else each.debit,

                })
            if len(transaction_list):
                return json.dumps({'status': True, 'message': _('Transation History.'), 'transaction_id': wallet_id,
                                   'history': transaction_list})
            else:
                return json.dumps({'status': True, 'message': _('No Transation History Found.')})
        except Exception as e:
            return json.dumps({'status': False, 'message': _(e)})

    @api.model
    def get_current_cart(self, kw):
        '''
            user_id = required
        '''
        user_id = kw.get('user_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        partner = user_id.partner_id
        order_id = self.env['sale.order'].sudo().search(
            [('partner_id', '=', partner.id), ('team_id.team_type', '=', 'website'), ('state', '=', 'draft')],
            order='id desc', limit=1)
        if not order_id:
            return json.dumps({'status': True, 'message': _('No Order Found.')})
        else:
            return json.dumps({'status': True, 'message': _('Order Found.'), 'cart_id': order_id.id,
                               'items': len(order_id.order_line)})

    @api.model
    def get_sms(self, kw):
        '''
            user_id = required
        '''
        user_id = kw.get('user_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        partner = user_id.partner_id
        sms = self.env['sms.message']
        domain = [
            ('to_mobile', 'ilike', partner.mobile)
        ]
        sms = sms.sudo().search(domain)
        if not sms:
            return json.dumps({'status': True, 'message': _('No SMS Found.')})
        else:
            return {'status': True, 'message': _('SMS Found.'), 'sms': sms.read()}

    @api.model
    def get_download_files(self, kw):
        '''
            user_id = required
        '''
        attachments = self.env['ir.attachment']
        domain = [
            ('public', '=', True),
            ('is_portal_visible', '=', True)
        ]
        attachments = attachments.sudo().search(domain)
        if not attachments:
            return json.dumps({'status': True, 'message': _('No Attachments Found.')})
        else:
            return {'status': True, 'message': _('Attachments Found.'), 'attachments': attachments.read()}

    @api.model
    def get_all_categories(self, kw):
        '''
            user_id = required
        '''

        categories = self.env['product.public.category'].sudo().search([])
        if not categories:
            return json.dumps({'status': True, 'message': _('No Categories Found.')})
        else:
            category_list = []
            for each in categories:
                child_id_list = []
                for child in each.child_id:
                    child_id_list.append(child.read())
                value = each.read()
                value[0].update({
                    'child_ids_list': child_id_list
                })
                category_list.append(value)
            return {'status': True, 'message': _('Categories Found.'), 'categories': category_list}

    @api.model
    def confirm_sale_order(self, kw):
        '''
            user_id = required
            cart_id = required
            transaction_id = optional
            wallet_id = optional
        '''
        user_id = kw.get('user_id')
        cart_id = kw.get('cart_id')
        transaction_id = kw.get('transaction_id')
        wallet_id = kw.get('wallet_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        if not cart_id:
            return json.dumps({'status': False, 'message': _('Please provide cart id.')})
        if not transaction_id and not wallet_id:
            return json.dumps({'status': False, 'message': _('Please provide Transaction Id or Wallet Id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        cart_id = self.env['sale.order'].sudo().search([('id', '=', int(cart_id))])
        if not cart_id:
            return json.dumps({'status': False, 'message': _('Order not available in system.')})
        payment_acquirer = self.env['payment.acquirer'].sudo().search([('provider', '=', 'mygate')])
        ref = self.env['payment.transaction']._get_next_reference(cart_id.name,
                                                                  acquirer=payment_acquirer)
        carrier_id = self.env['delivery.carrier'].search(
            [('name', '=ilike', 'Free delivery charges')])
        cart_id.sudo().write({
            'carrier_id': carrier_id.id
        })
        tx_id = self.env['payment.transaction'].sudo().create({
            'reference': ref,
            'acquirer_id': payment_acquirer.id,
            'amount': cart_id.amount_total,
            'currency_id': cart_id.currency_id.id,
            'partner_id': user_id.partner_id.id,
            'sale_order_id': cart_id.id
        })
        if transaction_id:
            reference = transaction_id
        else:
            reference = "Paid From Wallet"
            payment = self.env['account.payment'].sudo().create({
                'payment_type': 'outbound',
                'payment_transaction_id': tx_id.id,
                'partner_id': user_id.partner_id.id,
                'partner_type': 'customer',
                'amount': cart_id.amount_total,
                'journal_id': payment_acquirer.journal_id.id,
                'payment_method_id': payment_acquirer.journal_id.inbound_payment_method_ids.id
            })
            payment.post()

        post = {
            '_TRANSACTIONINDEX': reference,
            '_AMOUNT': cart_id.amount_total,
            '_MERCHANTREFERENCE': ref,
            '_PANHASHED': True,
            '_RESULT': '0',
        }
        self.env['payment.transaction'].sudo().form_feedback(post, 'mygate')
        return json.dumps({'status': True, 'message': _('Order successfully Paid.')})

    @api.model
    def update_shipping_address(self, kw):
        '''
            user_id = required
            cart_id = required
            address_id = required
        '''
        user_id = kw.get('user_id')
        cart_id = kw.get('cart_id')
        address_id = kw.get('address_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        if not cart_id:
            return json.dumps({'status': False, 'message': _('Please provide cart id.')})
        if not address_id:
            return json.dumps({'status': False, 'message': _('Please provide Address Id or Wallet Id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        cart_id = self.env['sale.order'].sudo().search([('id', '=', int(cart_id))])
        if not cart_id:
            return json.dumps({'status': False, 'message': _('Order not available in system.')})
        else:
            cart_id.sudo().write({
                'partner_shipping_id': int(address_id)
            })
            return json.dumps({'status': True, 'message': _('Shipping Address Updated.')})

    @api.model
    def update_delivery_method(self, kw):
        '''
            user_id = required
            cart_id = required
            delivery_id = required
        '''
        user_id = kw.get('user_id')
        cart_id = kw.get('cart_id')
        delivery_id = kw.get('delivery_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        if not cart_id:
            return json.dumps({'status': False, 'message': _('Please provide cart id.')})
        if not delivery_id:
            return json.dumps({'status': False, 'message': _('Please provide Delivery Id or Wallet Id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        cart_id = self.env['sale.order'].sudo().search([('id', '=', int(cart_id))])
        if not cart_id:
            return json.dumps({'status': False, 'message': _('Order not available in system.')})
        else:
            cart_id.sudo().write({
                'carrier_id': int(delivery_id)
            })
            cart_id.sudo().get_delivery_price()
            cart_id.sudo().set_delivery_line()
            return json.dumps({'status': True, 'message': _('Order Delivery Method updated.'), 'cart_id': cart_id.id,
                               'cart_total': cart_id.amount_total})

    @api.model
    def get_all_delivery_methods(self, kw):
        '''
            user_id = required
        '''
        delivery_methods = self.env['delivery.carrier'].sudo().search([('website_published', '=', True)])
        if not delivery_methods:
            return json.dumps({'status': True, 'message': _('No Delivery Method Found.')})
        else:
            return {'status': True, 'message': _('Delivery Methods Found.'),
                    'delivery_methods': delivery_methods.read()}

    @api.model
    def get_all_tickets(self, kw):
        '''
            user_id = required
        '''
        user_id = kw.get('user_id')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        else:
            ticket_ids = self.env['helpdesk.ticket'].sudo().search([('partner_id', '=', user_id.partner_id.id)])
            if ticket_ids:
                return {'status': True, 'message': _('Tickets Found.'), 'tickets': ticket_ids.read()}
            else:
                return json.dumps({'status': False, 'message': _('No Tickets Found.')})

    @api.model
    def suggest_feature(self, kw):
        '''
            user_id = required
            subject = required
            suggestion = required
        '''
        user_id = kw.get('user_id')
        subject = kw.get('subject')
        suggestion = kw.get('suggestion')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        if not subject:
            return json.dumps({'status': False, 'message': _('Please provide subject.')})
        if not suggestion:
            return json.dumps({'status': False, 'message': _('Please provide suggestion.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        else:
            support_team = request.env['helpdesk.team'].sudo().search([('name', '=', 'Support')])
            ticket = request.env['helpdesk.ticket'].sudo().create({
                'name': kw.get('subject'),
                'description': kw.get('suggestion'),
                'partner_id': user_id.partner_id.id,
                'team_id': support_team.id
            })
            return json.dumps({'status': True, 'message': _('Feature request submitted.'), 'ticket': ticket.id})

    @api.model
    def submit_ticket(self, kw):
        '''
            user_id = required
            title = required
            description = required
        '''
        user_id = kw.get('user_id')
        title = kw.get('title')
        description = kw.get('description')
        if not user_id:
            return json.dumps({'status': False, 'message': _('Please provide user id.')})
        if not title:
            return json.dumps({'status': False, 'message': _('Please provide title.')})
        if not description:
            return json.dumps({'status': False, 'message': _('Please provide description.')})
        user_id = self.env['res.users'].sudo().search([('id', '=', int(user_id))])
        if not user_id:
            return json.dumps({'status': False, 'message': _('User not available in system.')})
        else:
            support_team = self.env['helpdesk.team'].sudo().search([('name', '=', 'Support')])
            ticket = self.env['helpdesk.ticket'].sudo().create({
                'name': kw.get('title'),
                'description': kw.get('description'),
                'partner_id': user_id.partner_id.id,
                'team_id': support_team.id
            })
            return json.dumps({'status': True, 'message': _('Ticket submitted.'), 'ticket': ticket.id})
