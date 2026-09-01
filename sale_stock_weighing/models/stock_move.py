import ast

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class StockMove(models.Model):
    _name = "stock.move"
    _inherit = ["stock.move", "weighing.mixin"]

    recorded_weight = fields.Float(
        string="Peso Registrado",
        compute="_compute_recorded_weight",
        inverse="_inverse_recorded_weight",
        digits="Product Unit of Measure",
        help="Peso total de la operación. Editable en modo grilla: se reparte "
        "entre las líneas de detalle proporcionalmente a su cantidad.",
    )
    weighing_detail_level = fields.Selection(
        related="picking_type_id.weighing_detail_level",
        string="Nivel de detalle de pesaje",
    )
    weight_deviation_pct = fields.Float(
        string="Desvío",
        compute="_compute_weight_deviation_pct",
        help="Diferencia porcentual entre el peso real y el peso estimado. "
        "Sirve para detectar errores de carga.",
    )
    weighed_piece_count = fields.Integer(
        compute="_compute_piece_progress",
    )
    total_piece_count = fields.Integer(
        compute="_compute_piece_progress",
    )
    piece_progress = fields.Char(
        string="Piezas",
        compute="_compute_piece_progress",
        help="Piezas pesadas sobre el total de la línea.",
    )

    @api.depends("recorded_weight", "planned_weight")
    def _compute_weight_deviation_pct(self):
        for move in self:
            if move.planned_weight and move.recorded_weight:
                move.weight_deviation_pct = (
                    (move.recorded_weight - move.planned_weight)
                    / move.planned_weight
                    * 100
                )
            else:
                move.weight_deviation_pct = 0.0

    @api.depends(
        "move_line_ids.has_recorded_weight",
        "move_line_ids.quantity",
        "product_uom_qty",
        "weighing_detail_level",
    )
    def _compute_piece_progress(self):
        for move in self:
            relevant = move.move_line_ids._weighing_relevant()
            weighed = len(relevant.filtered("has_recorded_weight"))
            # En modo pieza el total esperado es la cantidad del movimiento;
            # si ya hay más líneas que la cantidad, manda la cantidad de líneas.
            expected = max(int(move.product_uom_qty or 0), len(move.move_line_ids))
            move.weighed_piece_count = weighed
            move.total_piece_count = expected
            if move.weighing_detail_level == "piece" and move.has_weight:
                move.piece_progress = "%d/%d" % (weighed, expected)
            else:
                move.piece_progress = ""
    move_lines_weighed = fields.Boolean(
        compute="_compute_recorded_weight",
    )
    weighing_state = fields.Selection(
        string="Estado de Pesaje",
        selection=[
            ("weighed", "Pesado"),
            ("weighing", "Pesando"),
            ("to_weigh", "Por pesar"),
        ],
        compute="_compute_weighing_state",
        store=True,
    )
    weighing_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Usuario de Pesaje",
        help="Usuario que está pesando esta operación. Bloquea la operación para otros usuarios.",
    )
    is_weighing_operation_locked = fields.Boolean(
        compute="_compute_is_weighing_operation_locked",
    )
    lot_names = fields.Char(
        compute="_compute_lot_names",
    )
    origin_names = fields.Char(
        compute="_compute_origin_names",
    )
    show_weighing_print_button = fields.Boolean(
        compute="_compute_show_weighing_print_button",
    )
    weighing_state_color = fields.Integer(
        compute="_compute_weighing_state_color",
    )
    weighing_uom_name = fields.Char(
        compute="_compute_weighing_uom_name",
    )
    planned_weight = fields.Float(
        string="Peso Estimado",
        compute="_compute_planned_weight",
        digits="Product Unit of Measure",
    )

    weight_is_quantity = fields.Boolean(
        string="La cantidad ya expresa el peso",
        compute="_compute_weight_is_quantity",
        help="La UdM del movimiento y la UdM de pesaje del producto son "
        "convertibles entre sí: la cantidad ya expresa el peso real y no hace "
        "falta el asistente de pesaje.",
    )

    @api.depends("has_weight", "product_id.weighing_uom_id", "product_uom")
    def _compute_weight_is_quantity(self):
        # Odoo 19: las UdM no tienen categoría, la compatibilidad se consulta
        # con _has_common_reference sobre el árbol de relative_uom_id.
        for move in self:
            weighing_uom = move.product_id.weighing_uom_id
            move.weight_is_quantity = bool(
                move.has_weight
                and weighing_uom
                and move.product_uom
                and weighing_uom._has_common_reference(move.product_uom)
            )

    @api.depends("product_id.weighing_uom_id")
    def _compute_weighing_uom_name(self):
        for move in self:
            move.weighing_uom_name = move.product_id.weighing_uom_id.name or "kg"

    @api.depends("product_id.weight", "product_uom_qty", "product_id.weighing_uom_id", "has_weight")
    def _compute_planned_weight(self):
        kg_uom = self.env.ref("uom.product_uom_kgm")
        for move in self:
            if not move.has_weight:
                move.planned_weight = 0.0
                continue
            weight = move.product_id.weight or 0.0
            weighing_uom = move.product_id.weighing_uom_id
            if weighing_uom and weighing_uom != kg_uom:
                try:
                    weight = kg_uom._compute_quantity(weight, weighing_uom)
                except Exception:
                    pass
            move.planned_weight = move.product_uom_qty * weight

    def _is_zero_quantity(self):
        """El movimiento no entrega nada: no hay qué pesar."""
        self.ensure_one()
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        return float_is_zero(self.quantity, precision_digits=precision)

    @api.depends(
        "move_line_ids.recorded_weight",
        "move_line_ids.has_recorded_weight",
        "move_line_ids.quantity",
    )
    def _compute_recorded_weight(self):
        for move in self:
            # Las líneas en cantidad cero no suman peso aunque lo tengan cargado.
            lines = move.move_line_ids._weighing_relevant()
            move.recorded_weight = sum(lines.mapped("recorded_weight"))
            move.move_lines_weighed = bool(lines) and all(
                lines.mapped("has_recorded_weight")
            )

    def _inverse_recorded_weight(self):
        """Distribuye el peso total del movimiento entre sus líneas de detalle.

        Se usa desde la grilla en modo "total por línea". El reparto es
        proporcional a la cantidad de cada línea; si las cantidades no están
        cargadas, se reparte en partes iguales. En el caso habitual — una sola
        línea de detalle — el peso va entero ahí.
        """
        for move in self:
            lines = move.move_line_ids
            if not lines:
                continue
            weight = move.recorded_weight or 0.0
            if not weight:
                lines.write(
                    {
                        "recorded_weight": 0.0,
                        "has_recorded_weight": False,
                        "weighing_user_id": False,
                        "weighing_date": False,
                    }
                )
                continue
            total_qty = sum(lines.mapped("quantity"))
            now = fields.Datetime.now()
            user_id = self.env.user.id
            assigned = 0.0
            for index, line in enumerate(lines):
                is_last = index == len(lines) - 1
                if is_last:
                    # La última absorbe el redondeo para que la suma cierre exacta.
                    share = weight - assigned
                elif total_qty:
                    share = weight * (line.quantity / total_qty)
                else:
                    share = weight / len(lines)
                assigned += share
                line.write(
                    {
                        "recorded_weight": share,
                        "has_recorded_weight": True,
                        "weighing_user_id": line.weighing_user_id.id or user_id,
                        "weighing_date": line.weighing_date or now,
                    }
                )

    @api.depends(
        "move_line_ids.recorded_weight",
        "move_line_ids.has_recorded_weight",
        "state",
        "product_id",
    )
    def _compute_weighing_state(self):
        self.weighing_state = False
        for move in self.filtered("has_weight"):
            move_to_do = move.state not in {"draft", "cancel", "done"}
            if not move_to_do:
                continue
            if move.move_lines_weighed:
                move.weighing_state = "weighed"
            elif move.recorded_weight:
                move.weighing_state = "weighing"
            else:
                move.weighing_state = "to_weigh"

    @api.depends("move_line_ids.lot_id")
    def _compute_lot_names(self):
        for move in self:
            move.lot_names = ", ".join(move.move_line_ids.lot_id.mapped("name"))

    @api.depends("move_line_ids.location_id")
    def _compute_origin_names(self):
        for move in self:
            move.origin_names = ", ".join(move.move_line_ids.location_id.mapped("name"))

    @api.depends("weighing_user_id", "state")
    def _compute_is_weighing_operation_locked(self):
        self.is_weighing_operation_locked = False
        locked_moves = self.filtered(
            lambda x: x.state not in {"cancel", "draft", "done"}
            and x.weighing_user_id
            and x.weighing_user_id != self.env.user
        )
        locked_moves.is_weighing_operation_locked = True

    @api.depends("quantity", "picking_type_id.weighing_operations")
    def _compute_show_weighing_print_button(self):
        for move in self:
            move.show_weighing_print_button = bool(
                move.quantity and move.picking_type_id.weighing_operations
            )

    @api.depends("weighing_state")
    def _compute_weighing_state_color(self):
        state_map = {"weighed": 10, "to_weigh": 1, "weighing": 3}
        for move in self:
            move.weighing_state_color = state_map.get(move.weighing_state, 0)

    def action_lock_weighing_operation(self):
        self.ensure_one()
        if self.weighing_user_id and self.weighing_user_id != self.env.user:
            raise UserError(
                _(
                    "El usuario %(user)s ya está pesando esta operación",
                    user=self.weighing_user_id.name,
                )
            )
        self.weighing_user_id = self.env.user

    def action_unlock_weigh_operation(self):
        self.ensure_one()
        self.weighing_user_id = False

    def _get_default_print_label(self):
        return self.picking_type_id.print_weighing_label

    def action_weighing(self):
        self.action_lock_weighing_operation()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sale_stock_weighing.weighing_wizard_action"
        )
        first_line = self.move_line_ids[:1]
        action["name"] = first_line._get_action_weighing_name() if first_line else action["name"]
        action["context"] = dict(
            self.env.context,
            default_selected_move_line_id=first_line.id if first_line else False,
            default_weight=self.recorded_weight or 0.0,
            default_move_line_ids=self.move_line_ids.ids,
            default_print_label=self._get_default_print_label(),
            default_move_id=self.id,
        )
        return action

    def _get_expected_piece_count(self):
        """Cantidad de piezas a pesar: lo que efectivamente se va a entregar,
        y si todavía no hay cantidad cargada, la demanda."""
        self.ensure_one()
        return int(self.quantity or self.product_uom_qty or 0)

    def _ensure_piece_move_lines(self):
        """Genera una línea de detalle por pieza para poder pesarlas una a una.

        Cada pieza es un stock.move.line de una unidad — la misma estructura que
        Odoo arma solo cuando el producto tiene seguimiento por lote. Las líneas
        existentes se reducen a una unidad y se crean las que falten, de modo que
        la suma siga dando la cantidad del movimiento.

        Nunca se borran líneas: si ya hay más de las esperadas, se deja como está.
        """
        self.ensure_one()
        if not self.has_weight:
            return
        if self.picking_type_id.weighing_detail_level != "piece":
            return
        expected = self._get_expected_piece_count()
        lines = self.move_line_ids
        if expected <= 1 or expected <= len(lines):
            return

        template = lines[:1]
        if template:
            lines.filtered(lambda line: line.quantity != 1).write({"quantity": 1.0})
            for _index in range(expected - len(lines)):
                template.copy(
                    {
                        "quantity": 1.0,
                        "recorded_weight": 0.0,
                        "has_recorded_weight": False,
                        "weighing_user_id": False,
                        "weighing_date": False,
                        "lot_id": False,
                    }
                )
            return

        # Sin líneas de detalle todavía (movimiento sin reservar): se arman
        # desde los datos del movimiento.
        self.env["stock.move.line"].create(
            [
                {
                    "move_id": self.id,
                    "picking_id": self.picking_id.id,
                    "product_id": self.product_id.id,
                    "product_uom_id": self.product_uom.id,
                    "quantity": 1.0,
                    "location_id": self.location_id.id,
                    "location_dest_id": self.location_dest_id.id,
                }
                for _index in range(expected)
            ]
        )

    def action_weight_detailed_operations(self):
        self.ensure_one()
        self._ensure_piece_move_lines()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sale_stock_weighing.weighing_operation_action"
        )
        # En diálogo: si se llega desde la grilla (que ya es un popup), abrir a
        # pantalla completa cerraría la carga de pesos a medio hacer.
        action["target"] = "new"
        action["display_name"] = _(
            # stock.move no tiene campo name en Odoo 19: se usa el producto.
            "Operaciones detalladas de %(name)s",
            name=self.product_id.display_name,
        )
        action["domain"] = [("id", "=", self.id)]
        action["view_mode"] = "form"
        action["res_id"] = self.id
        action["views"] = [
            (view, mode) for view, mode in action["views"] if mode == "form"
        ]
        action["context"] = dict(
            self.env.context,
            **ast.literal_eval(action.get("context", "{}") or "{}"),
            weight_operation_details=True,
        )
        action["context"].pop("show_weight_detail_buttons", None)
        return action

    def action_print_weight_record_label(self):
        """Imprime las etiquetas de las piezas de estos movimientos.

        Sirve tanto para una operación sola (botón de la tarjeta) como para una
        selección desde la grilla, donde se emite un único trabajo con todas las
        etiquetas. El formato — PDF o ZPL para la impresora de la IoT — lo define
        el tipo de operación.

        Se imprimen todas las piezas, estén pesadas o no: la etiqueta sin peso
        sirve para pegarla y completarla a mano.
        """
        lines = self.move_line_ids
        if not lines:
            raise UserError(
                _("Las operaciones seleccionadas no tienen piezas para etiquetar.")
            )
        return lines.action_print_weight_record_label()

    def action_reset_weights(self):
        self.move_line_ids.action_reset_weights()

    def action_force_weighed(self):
        self.weighing_state = "weighed"
