from odoo import models


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    def _compute_estimated_shipping_capacity(self):
        """Usa el peso real registrado en lugar del teórico del maestro.

        El cálculo del core suma, para cada línea suelta (sin paquete con peso
        propio), ``product.weight × cantidad``. Para productos pesables ese peso
        es una estimación —y en muchos casos está en cero, porque para algo que
        se vende por kg el dato no significa nada—, así que la capacidad usada
        del vehículo daba cero.

        En lugar de reescribir el cálculo del core, se lo deja correr y se le
        aplica la diferencia entre el peso real y el teórico de las líneas que sí
        fueron pesadas. Así cualquier cambio futuro en la lógica de paquetes de
        Odoo sigue vigente.

        Lo consume stock_fleet para used_weight_percentage, la barra de carga del
        vehículo en el traslado por lote.
        """
        super()._compute_estimated_shipping_capacity()
        for batch in self:
            # Mismo criterio que el core: un paquete con shipping_weight propio
            # ya aportó su peso, así que sus líneas no se vuelven a contar.
            packed_ids = {
                pack.id
                for pack in batch.move_line_ids.result_package_id
                if pack.shipping_weight
            }
            delta = 0.0
            lines = batch.picking_ids.move_ids.move_line_ids._weighing_relevant()
            for line in lines.filtered("has_recorded_weight"):
                if line.result_package_id.id in packed_ids:
                    continue
                teorico = line.product_id.weight * line.quantity_product_uom
                delta += line.recorded_weight - teorico
            if delta:
                batch.estimated_shipping_weight += delta
