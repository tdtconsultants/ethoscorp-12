# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools



class SaleOrder(models.Model):
    
    _inherit = 'purchase.order'

    ec_short_description = fields.Text(u"Short description")

