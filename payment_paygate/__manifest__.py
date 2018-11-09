# -*- coding: utf-8 -*-
{
    'name': "payment_paygate",
    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",
    'description': """
        Long description of module's purpose
    """,
    'author': "My Company",
    'website': "http://www.yourcompany.com",
    'category': 'Payment Acquirer',
    'version': '1.0',
    'depends': ['payment', 'website_sale'],
    'data': [
        'views/paygate_template.xml',
        'data/payment_acquirer_data.xml',
    ],
}