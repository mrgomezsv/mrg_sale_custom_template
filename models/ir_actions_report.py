# -*- coding: utf-8 -*-

from odoo import models

# Acciones que también imprimen sale.report_saleorder_document (el documento
# personalizado): la de sale_pdf_quote_builder, que reemplaza a la estándar en el
# menú Imprimir cuando está instalado, y la factura proforma.
CUSTOM_DOCUMENT_REPORTS = ('sale.report_saleorder_raw', 'sale.report_saleorder_pro_forma')


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def get_paperformat(self):
        # El diseño tiene alto fijo pensado para paperformat_mario; con el formato
        # por defecto de la compañía el contenido se desborda a una segunda página.
        if not self.paperformat_id and self.model == 'sale.order' and self.report_name in CUSTOM_DOCUMENT_REPORTS:
            paperformat = self.env.ref('mrg_sale_custom_template.paperformat_mario', raise_if_not_found=False)
            if paperformat:
                return paperformat
        return super().get_paperformat()
