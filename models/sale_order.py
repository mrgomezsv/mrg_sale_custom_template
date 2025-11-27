# -*- coding: utf-8 -*-

from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    mr_personalised_message = fields.Html(
        string='Mensaje Personalizado',
        default='Mediante la presente le envío la cotización que me solicitó para la fabricación del siguiente equipo:',
        help='Este mensaje aparecerá en el PDF de la cotización, justo después de la información del cliente y antes de la tabla de productos. Puedes personalizarlo según las necesidades de cada cotización, pero recuerde que "Mientras más caracteres contenga este campo el cuerpo de la cotizacion ira descendiendo"',
    )

