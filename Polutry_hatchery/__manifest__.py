{
    'name': 'Hatchery',
    'version': '1.0',
    'category': 'Agriculture',
    'summary': 'Manage Hatchery Egg Batches and Setters',
    'sequence': 10,
    'author': 'Betopia',   # <-- add your name or organization
    'website': 'https://yourcompany.com',  # optional
    'license': 'LGPL-3',  # recommended for Odoo modules
    'depends': ['base', 'mail', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/egg_batch_views.xml',
        'views/egg_break_wizard_view.xml',
        'views/setter_stage_views.xml',
        'views/hatcher_stage_views.xml',
        'views/chick_packaging_views.xml', 
        'views/internal_transfer_views.xml',  
        'views/product_template_views.xml',
        # 'views/setter_views.xml',  # if implementing setter menu
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
