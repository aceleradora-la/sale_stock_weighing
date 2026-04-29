/** @odoo-module **/

import { Component } from "@odoo/owl";

export class WeighingKanban extends Component {
    static template = "sale_stock_weighing.WeighingKanban";

    async onWeigh(record) {
        await this.env.services.action.doAction("sale_stock_weighing.weighing_wizard_action", {
            additionalContext: {
                default_selected_move_line_id: record.resId,
                default_weight: record.data.recorded_weight || record.data.quantity,
                default_move_line_ids: [record.resId],
                default_print_label: false,
            },
        });
        this.props.record.model.load();
    }

    async onReset(record) {
        const orm = this.env.services.orm;
        await orm.call("stock.move.line", "action_reset_weights", [[record.resId]]);
        this.props.record.model.load();
    }

    async onPrint(record) {
        await this.env.services.action.doAction("sale_stock_weighing.action_report_weighing_label", {
            additionalContext: {
                active_ids: [record.resId],
                active_model: "stock.move.line",
            },
        });
    }
}
