# -*- coding: utf-8 -*-
{
    'name': "odoo office 365",

    'summary': """
        Odoo is a fully integrated suite of business modules that encompass the traditional ERP functionality.
                Odoo Office365 Connector provides the opportunity to sync calendar between ODOO and Office365.
            """,

    'description': """
        -
    """,
    'author': "Techloyce",
    'website': "http://www.techloyce.com",
    'category': 'sale',
    'price': 499,
    'currency': 'EUR',
    "license": "LGPL-3", 
    'version': '0.1',
    'depends': ['base', 'calendar', 'sale_management', 'crm'],
    'images': [
        'static/description/icon.png',
    ],
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'data/scheduler.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
