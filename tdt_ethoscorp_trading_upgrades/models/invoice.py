# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools



class Invoice(models.Model):

    _inherit = 'account.invoice'

    ec_short_description = fields.Text(u"Short description")

