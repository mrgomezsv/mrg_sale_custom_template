# -*- coding: utf-8 -*-

from odoo import models
import re
import html


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def get_note_as_single_line(self):
        """Convierte el campo note (HTML) a texto plano en una sola línea"""
        return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', self.note or ''))).strip()

