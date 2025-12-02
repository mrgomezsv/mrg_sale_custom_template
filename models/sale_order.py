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
        """Obtiene información de los grupos de impuestos aplicados en el pedido"""
        tax_groups = {}
        for line in self.order_line:
            if line.display_type or line.is_downpayment:
                continue
            for tax in line.tax_id:
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

    def get_iva_info(self):
        """Obtiene información del IVA (impuesto que no es retención)"""
        tax_groups = self.get_tax_groups_info()
        for group_info in tax_groups.values():
            group_name = group_info['name'].lower()
            if 'retención' not in group_name and 'retencion' not in group_name:
                base = sum(line.price_subtotal for line in self.order_line 
                          if not line.display_type and not line.is_downpayment)
                avg_amount = sum(tax.amount for tax in group_info['taxes']) / len(group_info['taxes']) if group_info['taxes'] else 0
                iva_amount = round(base * (avg_amount / 100.0), 2)
                return {
                    'name': group_info['name'],
                    'amount': iva_amount,
                    'tax_rate': avg_amount
                }
        return None

    def get_retencion_info(self, base_amount=None):
        """Obtiene información de la retención IVA
        
        :param base_amount: Base sobre la cual calcular la retención (normalmente subtotal con IVA)
        """
        tax_groups = self.get_tax_groups_info()
        for group_info in tax_groups.values():
            group_name = group_info['name'].lower()
            if 'retención' in group_name or 'retencion' in group_name:
                avg_amount = sum(abs(tax.amount) for tax in group_info['taxes']) / len(group_info['taxes']) if group_info['taxes'] else 0
                if base_amount is None:
                    base_amount = sum(line.price_total for line in self.order_line 
                                     if not line.display_type and not line.is_downpayment)
                retencion_amount = round(base_amount * (avg_amount / 100.0), 2)
                return {
                    'name': group_info['name'],
                    'amount': retencion_amount,
                    'tax_rate': avg_amount
                }
        return None

    def get_all_taxes_ordered(self, base_amount, subtotal_with_taxes):
        """Obtiene todos los impuestos individuales ordenados: IVA primero, Retención IVA después, luego los demás
        
        Usa los valores calculados por Odoo agrupados por tax_group_id para mantener el redondeo correcto.
        
        :param base_amount: Base sin impuestos (subtotal después de descuentos)
        :param subtotal_with_taxes: Subtotal con todos los impuestos aplicados (no usado)
        :return: Lista de diccionarios con información de impuestos ordenados (cada impuesto por separado)
        """
        from collections import defaultdict
        from odoo.tools import float_round
        
        order_lines = self.order_line.filtered(lambda x: not x.display_type and not x.is_downpayment)
        if not order_lines:
            return []
        
        tax_totals = self.env['account.tax']._prepare_tax_totals(
            [line._convert_to_tax_base_line_dict() for line in order_lines],
            self.currency_id or self.company_id.currency_id,
        )

        tax_groups_info = {}
        groups_by_subtotal = tax_totals.get('groups_by_subtotal', {})
        
        if not groups_by_subtotal:
            tax_groups_amount = defaultdict(float)
            tax_groups_data = {}
            
            for line in order_lines:
                line_base = line.price_subtotal
                if line_base > 0:
      
                    for tax in line.tax_id:
                        if tax.tax_group_id:
                            group_id = tax.tax_group_id.id
                            
                
                            tax_compute = tax.with_company(line.company_id).compute_all(
                                line_base,
                                currency=line.order_id.currency_id,
                                quantity=1.0,
                                product=line.product_id,
                                partner=line.order_id.partner_id
                            )
                            
                         
                            tax_amount_line = sum(t.get('amount', 0.0) for t in tax_compute.get('taxes', []))
                            tax_groups_amount[group_id] += tax_amount_line
                            
                        
                            if group_id not in tax_groups_data:
                                group_name_lower = tax.tax_group_id.name.lower()
                                order = 1 
                                if 'retención' in group_name_lower or 'retencion' in group_name_lower:
                                    order = 2 
                                elif 'iva' in group_name_lower and 'retención' not in group_name_lower and 'retencion' not in group_name_lower:
                                    order = 1  
                                else:
                                    order = 3 
                                
                                tax_groups_data[group_id] = {
                                    'name': tax.tax_group_id.name,
                                    'order': order,
                                    'tax': tax 
                                }
            
            for group_id, amount in tax_groups_amount.items():
                if group_id in tax_groups_data and amount != 0:
                    tax_groups_info[group_id] = {
                        'name': tax_groups_data[group_id]['name'],
                        'amount': amount,
                        'order': tax_groups_data[group_id]['order'],
                        'tax': tax_groups_data[group_id].get('tax')
                    }
        else:
            for subtotal_key, groups_data in groups_by_subtotal.items():
                for group_data in groups_data:
                    group_id = group_data.get('tax_group_id')
                    if group_id:
                        tax_group_name = group_data.get('tax_group_name', '')
                        tax_group_amount = group_data.get('tax_group_amount', 0.0)
                        
                        group_name_lower = tax_group_name.lower()
                        order = 1 
                        if 'retención' in group_name_lower or 'retencion' in group_name_lower:
                            order = 2
                        elif 'iva' in group_name_lower and 'retención' not in group_name_lower and 'retencion' not in group_name_lower:
                            order = 1 
                        else:
                            order = 3 
                        

                        if group_id in tax_groups_info:
                            tax_groups_info[group_id]['amount'] += tax_group_amount
                        else:
                            tax_groups_info[group_id] = {
                                'name': tax_group_name,
                                'amount': tax_group_amount,
                                'order': order
                            }
        
        taxes_list = []
        for group_id, group_info in tax_groups_info.items():
            if group_info['amount'] != 0:
                if group_info['order'] == 2:
                    retencion_tax = group_info.get('tax')
                    if not retencion_tax:
                        for line in order_lines:
                            for tax in line.tax_id:
                                if tax.tax_group_id and tax.tax_group_id.id == group_id:
                                    retencion_tax = tax
                                    break
                            if retencion_tax:
                                break
                    
                    if retencion_tax:
                        tax_amount = float_round(base_amount * (abs(retencion_tax.amount) / 100.0), precision_digits=2)
                    else:
                        tax_amount = float_round(group_info['amount'], precision_digits=2)
                else:
                    tax_amount = float_round(group_info['amount'], precision_digits=2)
                
                taxes_list.append({
                    'name': group_info['name'],
                    'amount': tax_amount,
                    'order': group_info['order']
                })

        taxes_list = sorted(taxes_list, key=lambda x: (x['order'], x['name']))
        
        return taxes_list

