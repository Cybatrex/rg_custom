{
    'name': "Inuka Customisations",
    'version': '1.5',
    'depends': ['sale', 'inuka', 'account_asset', 'purchase_requisition'],
    'licence': 'AGPL-3',
    'author': "Mziwakhe - Systemworks",
    'category': 'All',
    'complexity': "normal",
    'description': "Inuka Customisations by Systemworks",
    'data': [
        'views/res_partner_view.xml',
        'views/account_invoice_view.xml',
        'views/report_invoice.xml',
        'views/res_country_view.xml',
        'views/res_company_view.xml',
        'security/security.xml',
        'views/sales_view.xml',
        'views/purchase_view.xml',
        'views/stock_view.xml',
        'views/report_sale.xml'
     ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False
}
