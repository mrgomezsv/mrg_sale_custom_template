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

    def get_tax_groups_info(self):
        """Obtiene información de los grupos de impuestos aplicados en el pedido (tasas, no montos)"""
        tax_groups = {}
        for line in self.order_line:
            if line.display_type or line.is_downpayment:
                continue
            for tax in line.tax_ids:
                if tax.tax_group_id:
                    group_id = tax.tax_group_id.id
                    if group_id not in tax_groups:
                        tax_groups[group_id] = {
                            'name': tax.tax_group_id.name,
                            'amount': tax.amount,
                            'taxes': []
                        }
                    if tax.id not in [t.id for t in tax_groups[group_id]['taxes']]:
                        tax_groups[group_id]['taxes'].append(tax)
        return tax_groups

    def _get_report_tax_groups(self):
        """Grupos de impuestos del pedido con los montos que calcula Odoo.

        Los montos salen de tax_totals: el mismo cálculo y redondeo del total del
        pedido y de la factura. Antes se aplicaba la tasa del impuesto a la base de
        todas las líneas, lo que daba otro monto cuando el impuesto (p. ej. la
        retención) no aplica a todas las líneas.

        :return: lista de dict con 'name', 'amount' (con el signo de Odoo),
                 'order' (1 IVA, 2 retención, 3 otros) y 'taxes' (account.tax)
        """
        self.ensure_one()
        currency = self.currency_id or self.company_id.currency_id
        groups = []
        for subtotal in (self.tax_totals or {}).get('subtotals', []):
            for group_data in subtotal.get('tax_groups', []):
                amount = group_data.get('tax_amount_currency', 0.0)
                if currency.is_zero(amount):
                    continue
                name = group_data.get('group_name') or ''
                taxes = self.env['account.tax'].browse(group_data.get('involved_tax_ids') or [])
                group_name_lower = name.lower()
                # Retención por el nombre del grupo o porque sus impuestos restan (tasa
                # negativa), igual que el DTE identifica el IVA retenido.
                if ('retención' in group_name_lower or 'retencion' in group_name_lower
                        or (taxes and all(tax.amount < 0 for tax in taxes))):
                    order = 2
                elif 'iva' in group_name_lower:
                    order = 1
                else:
                    order = 3
                groups.append({
                    'name': name,
                    'amount': amount,
                    'order': order,
                    'taxes': taxes,
                })
        return groups

    def get_iva_info(self):
        """Obtiene información del IVA (primer grupo que no es retención) con el monto calculado por Odoo"""
        for group in self._get_report_tax_groups():
            if group['order'] != 2:
                taxes = group['taxes']
                return {
                    'name': group['name'],
                    'amount': group['amount'],
                    'tax_rate': sum(taxes.mapped('amount')) / len(taxes) if taxes else 0,
                }
        return None

    def get_retencion_info(self, base_amount=None):
        """Obtiene información de la retención con el monto calculado por Odoo (en positivo)

        :param base_amount: se conserva por compatibilidad; el monto ya no se recalcula
                            sobre una base, sale del cálculo de impuestos de Odoo
        """
        for group in self._get_report_tax_groups():
            if group['order'] == 2:
                taxes = group['taxes']
                return {
                    'name': group['name'],
                    'amount': abs(group['amount']),
                    'tax_rate': sum(abs(rate) for rate in taxes.mapped('amount')) / len(taxes) if taxes else 0,
                }
        return None

    def get_all_taxes_ordered(self, base_amount=None, subtotal_with_taxes=None):
        """Obtiene los impuestos del pedido por grupo, ordenados: IVA primero, retenciones después, luego los demás

        Los montos son los que calcula Odoo (ver _get_report_tax_groups). Las retenciones
        se devuelven en positivo porque el PDF las resta del subtotal.

        :param base_amount: se conserva por compatibilidad; ya no se usa
        :param subtotal_with_taxes: se conserva por compatibilidad; ya no se usa
        :return: lista de dict con 'name', 'amount' y 'order'
        """
        currency = self.currency_id or self.company_id.currency_id
        taxes_list = [{
            'name': group['name'],
            'amount': currency.round(abs(group['amount']) if group['order'] == 2 else group['amount']),
            'order': group['order'],
        } for group in self._get_report_tax_groups()]
        return sorted(taxes_list, key=lambda x: (x['order'], x['name']))


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_custom_report_discount(self):
        """Base sin descuento y descuento de la línea para el PDF personalizado.

        Se reconstruyen desde price_subtotal (lo que calcula Odoo) para que la 'Suma'
        del PDF cuadre con el subtotal real del pedido.

        :return: tupla (base sin descuento, descuento)
        """
        self.ensure_one()
        if not self.discount:
            return self.price_subtotal, 0.0
        if self.discount < 100:
            base = self.price_subtotal / (1 - (self.discount / 100.0))
        else:
            # Con 100 % de descuento el subtotal es 0: la base es el precio por la cantidad
            base = self.price_unit * self.product_uom_qty
        return base, base - self.price_subtotal

    def _get_custom_report_section_values(self):
        """Totales de las líneas de una sección o subsección, incluidas las que el
        reporte oculta (Odoo 20: 'ocultar composición')."""
        self.ensure_one()
        values = {'total': 0.0, 'base': 0.0, 'discount': 0.0}
        for line in self._get_section_lines():
            if line.display_type or line.is_downpayment:
                continue
            base, discount = line._get_custom_report_discount()
            values['total'] += line.price_unit * line.product_uom_qty
            values['base'] += base
            values['discount'] += discount
        return values

    def _custom_report_hides_prices(self):
        """True si la sección o subsección que contiene la línea oculta sus precios
        (Odoo 20: 'ocultar precios'); en ese caso el total va en la fila de la sección."""
        self.ensure_one()
        section = self.parent_id
        return bool(section.collapse_prices or (
            section.display_type == 'line_subsection' and section.parent_id.collapse_prices
        ))


