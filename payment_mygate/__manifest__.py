# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'MygateGlobal Payment Acquirer',
    'category': 'Payment Acquirer',
    'summary': 'Payment Acquirer: MygateGlobal Implementation',
    'description': """
    MygateGlobal Payment Acquirer for India.

    MygateGlobal payment gateway supports only INR currency.
    """,
    'depends': ['payment', 'website_sale'],
    'data': [
        'views/payment_views.xml',
        'views/payment_mygateglobal_templates.xml',
        'data/payment_acquirer_data.xml',
    ],
}
