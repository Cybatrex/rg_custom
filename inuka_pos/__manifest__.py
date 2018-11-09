# -*- coding: utf-8 -*-
{
    'name': "inuka_pos",

    'summary': """
        Inuka Pos Customizations""",

    'description': """
        Long description of module's purpose
    """,

    'category': 'point_of_sale',

    # any module necessary for this one to work correctly
    'depends': ['base','point_of_sale'],

    # always loaded
    'data': [
        'views/templates.xml',
        'views/pos_config.xml',
    ],
    'qweb': ['static/src/xml/pos.xml'],
}