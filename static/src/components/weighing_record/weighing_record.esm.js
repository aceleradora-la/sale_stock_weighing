/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

export class WeighingRecord extends Component {
    static template = "sale_stock_weighing.WeighingRecord";
    static props = {
        record: Object,
        onSave: Function,
        onCancel: Function,
    };

    setup() {
        this.state = useState({
            weight: this.props.record.data.recorded_weight || this.props.record.data.quantity || 0,
            lot_id: this.props.record.data.lot_id?.[0] || false,
        });
    }

    async onSave() {
        const orm = this.env.services.orm;
        await orm.write("stock.move.line", [this.props.record.resId], {
            qty_picked: this.state.weight,
            recorded_weight: this.state.weight,
            has_recorded_weight: true,
            lot_id: this.state.lot_id,
        });
        this.props.onSave();
    }

    onCancel() {
        this.props.onCancel();
    }
}
