# -*- encoding: utf-8 -*-
{
    'name': 'Inuka Customer Portal',
    'version': '1.5',
    'category': 'Website',
    'summary': 'Inuka Customer Portal',
    'description': """Inuka Customer Portal.""",
    'depends': ['base','portal', 'website', 'inuka', 'sale', 'crm'],
    'data': [
        'security/ir.model.access.csv',
        'views/attachment.xml',
        'views/folder_data.xml',
        'views/templates.xml'
    ],
    'installable': True,
    'auto_install': False,
    'post_init_hook': 'post_init_check',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
