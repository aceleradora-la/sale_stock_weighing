// License: LGPL-3.0 or later
// © 2025 Aceleradora LA — ported from OCA/stock-weighing 18.0 (Tecnativa)

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

/**
 * Systray button that lets the current user quickly change their default
 * remote measure device without going into Preferences.
 *
 * Only shown when the user belongs to the Stock user group (so it doesn't
 * clutter the systray for non-warehouse users).
 */
export class RemoteDeviceSelectorMenu extends Component {
    static template = "web_widget_remote_measure.RemoteDeviceSelectorButton";
    static props = {};

    setup() {
        this.action = useService("action");
        this.state = useState({ visible: false, deviceName: "" });

        onWillStart(async () => {
            // Check if user has stock access (group_stock_user).
            const hasAccess = await user.hasGroup("stock.group_stock_user");
            if (!hasAccess) return;
            this.state.visible = true;
            await this._loadCurrentDevice();
        });
    }

    async _loadCurrentDevice() {
        try {
            const settings = await rpc("/web/dataset/call_kw", {
                model: "res.users.settings",
                method: "search_read",
                args: [[["user_id", "=", user.userId]]],
                kwargs: {
                    fields: ["remote_measure_device_id"],
                    limit: 1,
                },
            });
            if (settings.length && settings[0].remote_measure_device_id) {
                this.state.deviceName = settings[0].remote_measure_device_id[1] || "";
            }
        } catch {
            // Ignore.
        }
    }

    async onClickSelectDevice() {
        // Open the user's own res.users.settings record so they can pick a device.
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.users.settings",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            domain: [["user_id", "=", user.userId]],
        });
        // Refresh the displayed device name after the dialog closes.
        await this._loadCurrentDevice();
    }
}

registry.category("systray").add(
    "web_widget_remote_measure.device_selector",
    {
        Component: RemoteDeviceSelectorMenu,
        isDisplayed: () => true,
    },
    { sequence: 100 }
);
