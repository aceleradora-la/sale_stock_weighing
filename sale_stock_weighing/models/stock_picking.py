import ast

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    weighing_operations = fields.Boolean(
        related="picking_type_id.weighing_operations",
    )
    has_weighing_operations = fields.Boolean(
        compute="_compute_has_weighing_operations",
    )
    company_use_stock_weighing = fields.Boolean(
        related="company_id.use_stock_weighing",
        string="Empresa usa pesaje",
        store=False,  # no columna en DB — computed vía ir.config_parameter
    )

    @api.depends("move_ids.has_weight")
    def _compute_has_weighing_operations(self):
        for picking in self:
            picking.has_weighing_operations = bool(
                picking.move_ids.filtered("has_weight")
            )

    # ------------------------------------------------------------------
    # Bulk weight override
    # ------------------------------------------------------------------
    # Odoo core (_compute_bulk_weight en stock.picking) calcula el peso
    # como product.weight × quantity para todas las líneas sin paquete.
    # Para productos pesables usamos el peso real registrado (recorded_weight),
    # ya que product.weight refleja el peso estándar estimado, no el real.
    # Para productos no pesables se mantiene el cálculo estándar.
    # ------------------------------------------------------------------

    @api.depends(
        "move_line_ids",
        "move_line_ids.result_package_id",
        "move_line_ids.product_id",
        "move_line_ids.product_uom_id",
        "move_line_ids.quantity",
        "move_line_ids.recorded_weight",
        "move_line_ids.has_recorded_weight",
    )
    def _compute_bulk_weight(self):
        """Para productos pesables usa el peso real registrado (recorded_weight).
        Para productos sin pesaje usa el cálculo estándar (product.weight × qty)."""
        for picking in self:
            weight = 0.0
            bulk_lines = picking.move_line_ids.filtered(
                lambda ml: ml.product_id and not ml.result_package_id
            )
            for ml in bulk_lines:
                if ml.has_recorded_weight:
                    weight += ml.recorded_weight
                elif ml.weight_is_quantity:
                    # La cantidad ya es el peso, aunque todavía no se haya validado.
                    weight += ml._get_weight_from_quantity()
                else:
                    weight += (
                        ml.product_uom_id._compute_quantity(
                            ml.quantity, ml.product_id.uom_id
                        )
                        * ml.product_id.weight
                    )
            picking.weight_bulk = weight

    @api.depends(
        "move_line_ids.result_package_id",
        "move_line_ids.result_package_id.shipping_weight",
        "move_line_ids.recorded_weight",
        "move_line_ids.has_recorded_weight",
        "weight_bulk",
    )
    def _compute_shipping_weight(self):
        """Extiende el cálculo estándar para que los paquetes con productos pesables
        usen la suma de recorded_weight en lugar del peso estimado del maestro."""
        for picking in self:
            total = picking.weight_bulk
            for package in picking.move_line_ids.result_package_id:
                if package.shipping_weight:
                    # Peso configurado manualmente en el paquete → prioridad.
                    total += package.shipping_weight
                else:
                    pkg_lines = picking.move_line_ids.filtered(
                        lambda ml, p=package: ml.result_package_id == p
                    )
                    weighed = pkg_lines.filtered("has_recorded_weight")
                    if weighed:
                        # Paquete con productos pesados: peso real registrado.
                        total += sum(weighed.mapped("recorded_weight"))
                    else:
                        # Sin pesaje: cálculo estándar (product.weight × qty).
                        for ml in pkg_lines:
                            total += (
                                ml.product_uom_id._compute_quantity(
                                    ml.quantity, ml.product_id.uom_id
                                )
                                * ml.product_id.weight
                            )
            picking.shipping_weight = total

    def action_weighing_operations(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sale_stock_weighing.weighing_operation_action"
        )
        any_operation_actions = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sale_stock_weighing.any_operation_actions")
        )
        weight_moves = (
            self.move_ids
            if any_operation_actions
            else self.move_ids.filtered("has_weight")
        )
        action["name"] = _("Operaciones de pesaje de %(name)s", name=self.name)
        action["domain"] = [("id", "in", weight_moves.ids)]
        action["context"] = dict(
            self.env.context,
            **ast.literal_eval(action.get("context", "{}") or "{}"),
            group_by=["picking_id"],
        )
        picking_type = self[:1].picking_type_id
        if picking_type:
            picking_type._apply_weighing_view_mode(action)
        return action

    def _get_unweighed_moves(self):
        """Return moves that need weighing but haven't been fully weighed yet.

        Se excluyen los movimientos donde la cantidad ya expresa el peso
        (UdM de la línea y UdM de pesaje en la misma categoría): en esos casos
        no hay nada que pesar aparte, la cantidad cargada es el peso.

        Tampoco se exige pesaje si el tipo de operación no lo tiene habilitado."""
        self.ensure_one()
        if not self.picking_type_id.weighing_operations:
            return self.env["stock.move"]
        moves_to_weigh = self.move_ids.filtered(
            lambda m: m.has_weight and not m.weight_is_quantity
        )
        return moves_to_weigh.filtered(
            lambda m: not m.move_line_ids
            or not all(m.move_line_ids.mapped("has_recorded_weight"))
        )

    def button_validate(self):
        for picking in self:
            # Completa el peso desde la cantidad donde ambas son la misma
            # magnitud, antes de verificar qué falta pesar.
            picking.move_line_ids._sync_weight_from_quantity()
            unweighed = picking._get_unweighed_moves()
            if unweighed:
                raise UserError(
                    _(
                        "Las siguientes operaciones deben pesarse antes de validar %(picking)s:\n%(moves)s\n\n"
                        "Usá el asistente de pesaje para registrar los pesos.",
                        picking=picking.name,
                        moves="\n".join(
                            "- %s" % m.product_id.display_name for m in unweighed
                        ),
                    )
                )
        result = super().button_validate()
        # Actualizar shipping_weight en los paquetes que contienen productos
        # pesables, para que el reporte de entrega muestre el peso real en
        # lugar del peso estimado calculado desde el maestro del producto.
        self._update_weighed_package_shipping_weight()
        return result

    def _update_weighed_package_shipping_weight(self):
        """Escribe el peso registrado real en stock.quant.package.shipping_weight
        para los paquetes que contienen al menos una línea con peso registrado."""
        for picking in self:
            for package in picking.move_line_ids.result_package_id:
                pkg_lines = picking.move_line_ids.filtered(
                    lambda ml, p=package: ml.result_package_id == p
                )
                weighed = pkg_lines.filtered("has_recorded_weight")
                if weighed and not package.shipping_weight:
                    # Solo actualizar si no fue configurado manualmente.
                    package.sudo().shipping_weight = sum(
                        weighed.mapped("recorded_weight")
                    )
