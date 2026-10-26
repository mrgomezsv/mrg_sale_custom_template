# -*- coding: utf-8 -*-

from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.sale.tests.common import SaleCommon


@tagged('post_install', '-at_install')
class TestSaleCustomTemplate(SaleCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        TaxGroup = cls.env['account.tax.group']
        cls.iva = cls.env['account.tax'].create({
            'name': 'IVA 13%',
            'amount': 13.0,
            'tax_group_id': TaxGroup.create({'name': 'IVA 13%'}).id,
        })
        cls.retencion = cls.env['account.tax'].create({
            'name': 'Retención IVA 1%',
            'amount': -1.0,
            'tax_group_id': TaxGroup.create({'name': 'Retención IVA 1%'}).id,
        })
        # La retención aplica solo a la primera línea: el cálculo anterior la
        # aplicaba a la base de todo el pedido (2.50 en vez de 2.00).
        cls.order = cls._create_so(order_line=[
            Command.create({
                'product_id': cls.product.id,
                'product_uom_qty': 2.0,
                'price_unit': 100.0,
                'tax_ids': [Command.set((cls.iva + cls.retencion).ids)],
            }),
            Command.create({
                'product_id': cls.service_product.id,
                'product_uom_qty': 1.0,
                'price_unit': 50.0,
                'tax_ids': [Command.set(cls.iva.ids)],
            }),
        ])

    def _render_html(self, order):
        html = self.env['ir.actions.report']._render_qweb_html('sale.action_report_saleorder', order.ids)[0]
        return html.decode() if isinstance(html, bytes) else str(html)

    def test_impuestos_con_montos_de_odoo(self):
        self.assertAlmostEqual(self.order.amount_untaxed, 250.0)
        self.assertAlmostEqual(self.order.amount_total, 280.5)
        self.assertEqual(self.order.get_all_taxes_ordered(), [
            {'name': 'IVA 13%', 'amount': 32.5, 'order': 1},
            {'name': 'Retención IVA 1%', 'amount': 2.0, 'order': 2},
        ])
        self.assertEqual(self.order.get_iva_info()['amount'], 32.5)
        self.assertEqual(self.order.get_retencion_info()['amount'], 2.0)

    def test_pdf_renderiza_con_totales_de_odoo(self):
        """Odoo 20: sin hasattr ni company.mobile el reporte se genera, y sin t-esc los valores aparecen."""
        html = self._render_html(self.order)
        self.assertIn(self.order.name, html)
        # Odoo 20 guarda el nombre del producto en label, no en name
        self.assertIn('Test Product', html)
        self.assertIn('250.00', html)
        self.assertIn('32.50', html)
        self.assertIn('282.50', html)  # Sub - total
        self.assertIn('2.00', html)
        self.assertIn('280.50', html)  # TOTAL = total del pedido

    def test_seccion_que_oculta_composicion(self):
        order = self._create_so(order_line=[
            Command.create({
                'name': 'Tablero eléctrico',
                'display_type': 'line_section',
                'collapse_composition': True,
            }),
            Command.create({
                'product_id': self.product.id,
                'name': 'Breaker oculto',
                'product_uom_qty': 1.0,
                'price_unit': 40.0,
                'discount': 25.0,
                'tax_ids': [Command.set(self.iva.ids)],
            }),
        ])
        html = self._render_html(order)
        self.assertIn('Tablero eléctrico', html)
        self.assertNotIn('Breaker oculto', html)
        self.assertIn('40.00', html)  # total de la sección antes del descuento
        self.assertIn('DESCUENTO DEL 25', html)  # el descuento de la línea oculta también cuenta
        self.assertIn('33.90', html)  # TOTAL = 30.00 + IVA 3.90

    def test_seccion_que_oculta_precios(self):
        order = self._create_so(order_line=[
            Command.create({
                'name': 'Mano de obra',
                'display_type': 'line_section',
                'collapse_prices': True,
            }),
            Command.create({
                'product_id': self.service_product.id,
                'product_uom_qty': 3.0,
                'price_unit': 12.34,
                'tax_ids': [Command.set(self.iva.ids)],
            }),
            Command.create({'name': 'Instalación', 'display_type': 'line_subsection'}),
        ])
        self.assertTrue(order.order_line[1]._custom_report_hides_prices())
        html = self._render_html(order)
        self.assertIn('Instalación', html)
        self.assertIn('37.02', html)  # total de la sección
        self.assertNotIn('12.34', html)  # el precio unitario de la línea no se imprime

    def test_formato_de_papel_del_documento(self):
        paperformat = self.env.ref('mrg_sale_custom_template.paperformat_mario')
        self.assertEqual(self.env.ref('sale.action_report_saleorder').get_paperformat(), paperformat)
        # La proforma imprime el mismo documento personalizado
        self.assertEqual(self.env.ref('sale.action_report_pro_forma_invoice').get_paperformat(), paperformat)
