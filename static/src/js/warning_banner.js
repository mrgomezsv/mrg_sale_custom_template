/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class WarningBanner extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            enabled: false,
            warningText: '⚠️ FACTURA PENDIENTE DE PAGO'
        });

        onWillStart(async () => {
            try {
                const config = await this.orm.call(
                    'res.config.settings',
                    'get_warning_banner_status',
                    []
                );
                this.state.enabled = config.enable_warning_banner || false;
                this.state.warningText = config.warning_text || '⚠️ FACTURA PENDIENTE DE PAGO';
            } catch (error) {
                console.error('Error loading warning banner config:', error);
                this.state.enabled = false;
            }
        });
    }
}

WarningBanner.template = 'mrg_custom_warning_banner.WarningBanner';

// Registrar en el systray (barra superior)
registry.category('systray').add('warning_banner', {
    Component: WarningBanner,
    sequence: 1,
});