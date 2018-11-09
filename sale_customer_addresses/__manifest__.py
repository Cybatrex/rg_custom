{
    'name': 'Filter Customer Addresses',
    'version': '1.0',
    'summary': 'Shows customer\'s addresses by default',
    'description': '''Shows customers addresses by default when creating sales
orders and invoices.''',
    'category': 'Sales',
    'author': 'SystemWorks',
    'website': 'https://www.systemworks.co.za/',
    'depends': ['base', 'sale'],
    'data': [
        'views/sale_views.xml',
    ],
}
