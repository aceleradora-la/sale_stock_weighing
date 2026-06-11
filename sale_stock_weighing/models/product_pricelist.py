from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class Pricelist(models.Model):
    _inherit = "product.pricelist"

    company_use_stock_weighing = fields.Boolean(
        compute="_compute_company_use_stock_weighing",
        store=False,
    )

    @api.depends("company_id", "company_id.use_stock_weighing")
    def _compute_company_use_stock_weighing(self):
        for pl in self:
            company = pl.company_id or self.env.company
            pl.company_use_stock_weighing = company.use_stock_weighing

    def _get_matched_weighing_items(self, product, date=None):
        """Devuelve los ítems de precio por peso que aplican para el producto.

        Acepta tanto product.product como product.template — el reporte de
        lista de precios de Odoo pasa el template directamente.

        Filtra por vigencia (date_start/date_end) igual que el pricelist
        estándar, usando la fecha recibida o la actual.
        """
        self.ensure_one()
        date = date or fields.Datetime.now()
        if not isinstance(date, datetime):
            # acepta date (no datetime), como hace el pricelist estándar
            date = fields.Datetime.to_datetime(date)
        # Normalizar: obtener template y variante sin importar cuál se recibió.
        if product._name == "product.template":
            product_tmpl = product
            product_variant = product.product_variant_id  # primera variante
        else:
            product_tmpl = product.product_tmpl_id
            product_variant = product

        category_ids = set()
        cat = product.categ_id
        while cat:
            category_ids.add(cat.id)
            cat = cat.parent_id

        items = self.item_ids.filtered(
            lambda i: i.is_weighed_price
            and (not i.date_start or i.date_start <= date)
            and (not i.date_end or i.date_end >= date)
            and (
                (i.applied_on == "0_product_variant" and i.product_id == product_variant)
                or (i.applied_on == "1_product" and i.product_tmpl_id == product_tmpl)
                or (i.applied_on == "2_product_category" and i.categ_id.id in category_ids)
                or i.applied_on == "3_global"
            )
        )
        return items.sorted("min_quantity", reverse=True)

    def _get_product_price(self, product, quantity=1.0, *args, **kwargs):
        self.ensure_one()
        if product.is_weighed_product:
            matched = self._get_matched_weighing_items(product, date=kwargs.get("date"))
            if matched:
                return matched[0].compute_price_per_weight(product, quantity)
        return super()._get_product_price(product, quantity, *args, **kwargs)


class PricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    company_use_stock_weighing = fields.Boolean(
        related="pricelist_id.company_use_stock_weighing",
        store=False,
    )

    price_per_weight = fields.Float(
        string="Precio por Unidad de Peso",
        digits="Product Price",
        help="Precio por unidad de peso (ej: por kg) para productos pesables.",
    )
    is_weighed_price = fields.Boolean(
        string="Precio por Peso",
        help="Aplica las reglas de precio sobre el precio por kg, en lugar del precio por unidad.",
    )
    weighing_uom_name = fields.Char(
        string="UdM de Pesaje",
        compute="_compute_weighing_uom_name",
    )
    weight_price_display = fields.Char(
        string="Precio por Peso",
        compute="_compute_weight_price_display",
        help="Precio por peso efectivo expresado en $/UdM, calculado según la regla configurada.",
    )

    @api.depends(
        "product_id.weighing_uom_id",
        "product_tmpl_id.weighing_uom_id",
    )
    def _compute_weighing_uom_name(self):
        for item in self:
            item.weighing_uom_name = (
                item.product_id.weighing_uom_id.name
                or item.product_tmpl_id.weighing_uom_id.name
                or "kg"
            )

    @api.depends(
        "is_weighed_price",
        "compute_price",
        "price_per_weight",
        "price_discount",
        "price_surcharge",
        "base",
        "base_pricelist_id",
        "weighing_uom_name",
    )
    def _compute_weight_price_display(self):
        for item in self:
            if not item.is_weighed_price:
                item.weight_price_display = ""
                continue
            uom = item.weighing_uom_name or "kg"
            if item.compute_price == "fixed":
                item.weight_price_display = "%.2f / %s" % (
                    item.price_per_weight or 0.0,
                    uom,
                )
                continue
            if item.compute_price in ("discount", "formula"):
                base_label = (
                    item.base_pricelist_id.display_name
                    if item.base == "pricelist" and item.base_pricelist_id
                    else (item.base or "")
                )
                pct = item.price_discount or 0.0
                op = "−" if item.compute_price == "discount" else "+"
                surcharge = (
                    " + %.2f" % item.price_surcharge if item.price_surcharge else ""
                )
                item.weight_price_display = "%s × (1 %s %.2f%%)%s / %s" % (
                    base_label,
                    op,
                    pct,
                    surcharge,
                    uom,
                )
                continue
            item.weight_price_display = ""

    @api.onchange("is_weighed_price", "compute_price")
    def _onchange_is_weighed_price(self):
        """For weighed pricing in Discount/Formula mode, the only sensible base
        is another pricelist (so the formula operates on $/weight, not on the
        product's per-unit list/standard price). Auto-set it on the form."""
        if (
            self.is_weighed_price
            and self.compute_price in ("discount", "formula")
            and self.base != "pricelist"
        ):
            self.base = "pricelist"

    @api.constrains("is_weighed_price", "compute_price", "base", "base_pricelist_id")
    def _check_weighed_base(self):
        for item in self:
            if not item.is_weighed_price:
                continue
            if item.compute_price in ("discount", "formula"):
                if item.base != "pricelist" or not item.base_pricelist_id:
                    raise ValidationError(
                        _(
                            "El precio por peso en modo Descuento o Fórmula debe usar 'Otra Lista de Precios' como base, con una lista configurada. De este modo el porcentaje se aplica sobre un precio por unidad de peso y no sobre el precio por unidad del producto."
                        )
                    )

    def compute_price_per_weight(self, product, quantity=1):
        self.ensure_one()
        if not self.is_weighed_price:
            return 0.0
        if self.compute_price == "fixed":
            return self.price_per_weight
        if self.compute_price in ("discount", "formula"):
            base_price = self._compute_base_price_for_weight(product)
            if base_price <= 0 and self.compute_price == "discount":
                return 0.0
            # discount subtracts the percentage, formula adds it (markup).
            sign = -1 if self.compute_price == "discount" else 1
            result = base_price * (1 + sign * (self.price_discount or 0) / 100)
            result += self.price_surcharge or 0.0
            cost = product.standard_price or 0.0
            if self.price_min_margin:
                result = max(result, cost + self.price_min_margin)
            if self.price_max_margin:
                result = min(result, cost + self.price_max_margin)
            return result
        return 0.0

    def _compute_base_price_for_weight(self, product):
        """Resolve the base price for a weighed Discount/Formula rule.

        For weighed pricing the base must be another pricelist whose own
        weighed rule yields a $/weight value. For non-weighed cases we keep
        the historical fall-backs (rarely useful but harmless)."""
        self.ensure_one()
        if self.base == "pricelist" and self.base_pricelist_id:
            return self.base_pricelist_id._get_product_price(product, 1.0)
        if self.base == "standard_price":
            return product.standard_price or 0.0
        if self.base == "list_price":
            return product.list_price or 0.0
        return 0.0
