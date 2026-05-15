// License: LGPL-3.0 or later
// © 2025 Aceleradora LA — ported from OCA/stock-weighing 18.0 (Tecnativa)

import { FloatField, floatField } from "@web/views/fields/float/float_field";
import { onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

/**
 * RemoteMeasureField — extends FloatField with a balance-icon button that
 * opens a WebSocket connection to a remote scale and feeds readings into
 * the field.
 *
 * Supported options (passed via `options` attribute in XML):
 *   - remote_device_field   {String}  Field on the same record that holds
 *                                     the Many2one to remote.measure.device.
 *   - uom_field             {String}  Field on the same record with the
 *                                     target UoM (for automatic conversion).
 *   - default_user_device   {Boolean} When true, fall back to the user's
 *                                     default device from preferences.
 *   - allow_additive_measure {Boolean} Show a "+" button to accumulate
 *                                     readings instead of replacing.
 *
 * F501 protocol message format (example):
 *   "ST,+00004.700kg\r\n"   → status=ST (stable), weight=4.700, unit=kg
 *   "US,+00000.000kg\r\n"   → status=US (unstable) → ignored
 */
export class RemoteMeasureField extends FloatField {
    static template = "web_widget_remote_measure.RemoteMeasureField";

    static props = {
        ...FloatField.props,
        remote_device_field: { type: String, optional: true },
        uom_field: { type: String, optional: true },
        default_user_device: { type: Boolean, optional: true },
        allow_additive_measure: { type: Boolean, optional: true },
    };

    static defaultProps = {
        ...FloatField.defaultProps,
        default_user_device: false,
        allow_additive_measure: false,
    };

    // Thermometer animation icons cycling while measuring.
    static ICONS = [
        "fa-thermometer-empty",
        "fa-thermometer-quarter",
        "fa-thermometer-half",
        "fa-thermometer-three-quarters",
        "fa-thermometer-full",
    ];

    setup() {
        super.setup();
        this.notification = useService("notification");
        this.measureState = useState({
            device: null,          // remote.measure.device record
            measuring: false,      // actively reading from device
            stopped: true,         // user clicked "stop"
            iconIndex: 0,
        });
        this._socket = null;
        this._lastMeasure = 0;

        onWillStart(async () => {
            await this._loadDevice();
        });

        onWillUnmount(() => {
            this._closeSocket();
        });
    }

    // ----------------------------------------------------------------
    // Getters
    // ----------------------------------------------------------------

    get currentIcon() {
        const icons = RemoteMeasureField.ICONS;
        return icons[this.measureState.iconIndex % icons.length];
    }

    // ----------------------------------------------------------------
    // Device loading
    // ----------------------------------------------------------------

    async _loadDevice() {
        // 1) Prefer the device from a Many2one field on the same record.
        const deviceField = this.props.remote_device_field;
        if (deviceField) {
            const fieldData = this.props.record.data[deviceField];
            const deviceId = Array.isArray(fieldData) ? fieldData[0] : fieldData;
            if (deviceId) {
                await this._fetchDevice(deviceId);
                return;
            }
        }
        // 2) Fall back to the user's default device.
        if (this.props.default_user_device) {
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
                    await this._fetchDevice(settings[0].remote_measure_device_id[0]);
                }
            } catch {
                // No settings record yet — that's fine, device stays null.
            }
        }
    }

    async _fetchDevice(deviceId) {
        try {
            const [device] = await rpc("/web/dataset/call_kw", {
                model: "remote.measure.device",
                method: "read",
                args: [
                    [deviceId],
                    [
                        "name",
                        "host",
                        "port",
                        "connection_mode",
                        "protocol",
                        "uom_id",
                        "read_instantly",
                        "non_stop_read",
                        "read_interval",
                    ],
                ],
                kwargs: {},
            });
            this.measureState.device = device;
        } catch {
            // Device was deleted or ACL issue — silently skip.
        }
    }

    // ----------------------------------------------------------------
    // User actions
    // ----------------------------------------------------------------

    async onMeasure() {
        if (!this.measureState.device) {
            this.notification.add(
                _t(
                    "No hay balanza configurada. Andá a Preferencias y configurá una por defecto."
                ),
                { type: "warning" }
            );
            return;
        }
        this.measureState.stopped = false;
        this.measureState.measuring = true;
        const mode = this.measureState.device.connection_mode;
        if (mode === "websocket") {
            this._connectWebSocket();
        } else {
            this.notification.add(
                _t("El modo de conexión '%(mode)s' no está soportado aún.", { mode }),
                { type: "warning" }
            );
            this.measureState.stopped = true;
            this.measureState.measuring = false;
        }
    }

    onStopMeasure() {
        this.measureState.stopped = true;
        this.measureState.measuring = false;
        this._closeSocket();
    }

    async onMeasureAdd() {
        const current = this.props.record.data[this.props.name] || 0;
        await this.props.record.update({
            [this.props.name]: current + this._lastMeasure,
        });
    }

    // ----------------------------------------------------------------
    // WebSocket connection
    // ----------------------------------------------------------------

    _connectWebSocket() {
        const { host, port, name } = this.measureState.device;
        const url = `ws://${host}:${port}`;
        try {
            this._socket = new WebSocket(url);
        } catch {
            this._onConnectionError(name);
            return;
        }

        this._socket.onopen = () => {
            // Connection established — start listening.
        };

        this._socket.onmessage = (event) => {
            if (!this.measureState.stopped) {
                this._processMessage(event.data);
            }
        };

        this._socket.onerror = () => {
            this._onConnectionError(name);
        };

        this._socket.onclose = () => {
            if (!this.measureState.stopped) {
                this.measureState.stopped = true;
                this.measureState.measuring = false;
            }
        };
    }

    _onConnectionError(deviceName) {
        this.notification.add(
            _t("No se pudo conectar a la balanza: %(device)s", { device: deviceName }),
            { type: "danger" }
        );
        this.measureState.stopped = true;
        this.measureState.measuring = false;
    }

    _closeSocket() {
        if (this._socket) {
            try {
                this._socket.close();
            } catch {
                // Ignore errors on close.
            }
            this._socket = null;
        }
    }

    // ----------------------------------------------------------------
    // Protocol parsing
    // ----------------------------------------------------------------

    _processMessage(raw) {
        const protocol = this.measureState.device?.protocol || "f501";
        if (protocol === "f501") {
            this._processMsgF501(raw);
        }
    }

    /**
     * Parse an F501 scale message.
     *
     * Format examples:
     *   "ST,+00004.700kg\r\n"  →  stable, 4.700 kg
     *   "US,+00000.000kg\r\n"  →  unstable → ignored
     *   "OL,+99999.999kg\r\n"  →  overload → ignored
     */
    _processMsgF501(msg) {
        // Status (2 chars), comma, optional sign, digits, decimal, digits, unit
        const match = msg.trim().match(/^(ST|US|OL),([+-]?\d+\.\d+)\s*(\w+)/);
        if (!match) return;
        const [, status, weightStr] = match;
        if (status !== "ST") return; // Only stable readings.
        const weight = parseFloat(weightStr);
        if (!isFinite(weight) || weight <= 0) return;
        this._setMeasure(weight);
    }

    // ----------------------------------------------------------------
    // Recording the measure
    // ----------------------------------------------------------------

    async _setMeasure(rawWeight) {
        this._lastMeasure = rawWeight;

        // Animate the thermometer icon.
        this.measureState.iconIndex =
            (this.measureState.iconIndex + 1) % RemoteMeasureField.ICONS.length;

        // Convert UoM if device and field use different units.
        const weight = await this._convertWeight(rawWeight);
        if (this.measureState.stopped) return;

        await this.props.record.update({ [this.props.name]: weight });

        // Stop after first stable reading unless non_stop_read is enabled.
        if (!this.measureState.device?.non_stop_read) {
            this.onStopMeasure();
        }
    }

    async _convertWeight(weight) {
        const uomField = this.props.uom_field;
        const device = this.measureState.device;
        if (!uomField || !device?.uom_id) return weight;

        const targetData = this.props.record.data[uomField];
        const targetUomId = Array.isArray(targetData) ? targetData[0] : null;
        const sourceUomId = Array.isArray(device.uom_id)
            ? device.uom_id[0]
            : device.uom_id;

        if (!targetUomId || targetUomId === sourceUomId) return weight;

        try {
            const uoms = await rpc("/web/dataset/call_kw", {
                model: "uom.uom",
                method: "read",
                args: [
                    [sourceUomId, targetUomId],
                    ["factor", "factor_inv", "uom_type", "category_id"],
                ],
                kwargs: {},
            });
            const src = uoms.find((u) => u.id === sourceUomId);
            const tgt = uoms.find((u) => u.id === targetUomId);
            if (src && tgt && src.category_id[0] === tgt.category_id[0]) {
                // Convert via the reference unit: weight_in_ref = weight / src.factor
                // weight_in_target = weight_in_ref * tgt.factor
                return (weight / src.factor) * tgt.factor;
            }
        } catch {
            // Conversion failed — use raw value.
        }
        return weight;
    }
}

registry.category("fields").add("remote_measure", {
    ...floatField,
    component: RemoteMeasureField,
    supportedOptions: [
        {
            label: _t("Campo del Dispositivo"),
            name: "remote_device_field",
            type: "string",
        },
        {
            label: _t("Campo de UdM"),
            name: "uom_field",
            type: "string",
        },
        {
            label: _t("Usar Balanza por Defecto del Usuario"),
            name: "default_user_device",
            type: "boolean",
        },
        {
            label: _t("Permitir Medición Acumulativa"),
            name: "allow_additive_measure",
            type: "boolean",
        },
    ],
});
