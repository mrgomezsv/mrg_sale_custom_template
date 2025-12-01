# -*- coding: utf-8 -*-

from odoo import models
import re
import html


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def get_note_as_single_line(self):
        """Convierte el campo note (HTML) a texto plano en una sola línea"""
        return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', self.note or ''))).strip()

    def get_delivery_days(self):
        """Calcula los días de entrega entre date_order y commitment_date"""
        if not self.date_order or not self.commitment_date:
            return None
        delta = self.commitment_date - self.date_order
        return delta.days

    def format_currency(self, amount):
        """Formatea un monto con separadores de miles (formato: 1,234.56)"""
        if amount is None:
            return '0.00'
        return '{:,.2f}'.format(float(amount))

