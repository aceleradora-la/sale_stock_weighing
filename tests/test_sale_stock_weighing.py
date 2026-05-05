from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSaleStockWeighing(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kg_uom = cls.env.ref("uom.product_uom_kgm")
        cls.unit_uom = cls.env.ref("uom.product_uom_unit")

        cls.product_cheese = cls.env["product.product"].create({
            "name": "Cheese Feta Bar",
            "type": "product",
            "is_weighed_product": True,
            "uom_id": cls.unit_uom.id,
            "uom_po_id": cls.unit_uom.id,
            "weighing_uom_id": cls.kg_uom.id,
            "weight": 0.5,
            "list_price": 10.0,
            "standard_price": 4.0,
        })
        cls.product_plain = cls.env["product.product"].create({
            "name": "Plain Box",
            "type": "product",
            "uom_id": cls.unit_uom.id,
            "uom_po_id": cls.unit_uom.id,
            "list_price": 25.0,
        })
        cls.partner = cls.env["res.partner"].create({"name": "Test Customer"})

        cls.location_stock = cls.env.ref("stock.stock_location_stock")
        cls.location_customer = cls.env.ref("stock.stock_location_customers")
        cls.picking_type_out = cls.env.ref("stock.picking_type_out")
        cls.picking_type_out.write({
            "weighing_operations": True,
            "print_weighing_label": False,
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_outgoing_picking(self, product, qty):
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": self.location_stock.id,
            "quantity": qty + 5.0,
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.picking_type_out.id,
            "location_id": self.location_stock.id,
            "location_dest_id": self.location_customer.id,
            "partner_id": self.partner.id,
            "move_ids": [(0, 0, {
                "name": "Deliver",
                "product_id": product.id,
                "product_uom": product.uom_id.id,
                "product_uom_qty": qty,
                "location_id": self.location_stock.id,
                "location_dest_id": self.location_customer.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        return picking

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_product_config(self):
        self.assertTrue(self.product_cheese.is_weighed_product)
        self.assertEqual(self.product_cheese.weighing_uom_id, self.kg_uom)

    def test_planned_weight(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.product_cheese.id,
                "product_uom_qty": 2,
                "price_unit": 10.0,
                "price_per_weight": 10.0,
            })],
        })
        line = order.order_line[0]
        self.assertAlmostEqual(line.total_planned_weight, 1.0, places=2)

    def test_has_weight_mixin(self):
        picking = self._make_outgoing_picking(self.product_cheese, 2.0)
        self.assertTrue(picking.move_ids[0].has_weight)
        self.assertFalse(self.product_plain.is_weighed_product)

    def test_validate_blocks_when_unweighed(self):
        picking = self._make_outgoing_picking(self.product_cheese, 2.0)
        with self.assertRaises(UserError):
            picking.button_validate()

    def test_validate_syncs_weight_to_quantity(self):
        picking = self._make_outgoing_picking(self.product_cheese, 2.0)
        line = picking.move_ids[0].move_line_ids[:1]
        line.write({
            "recorded_weight": 0.980,
            "has_recorded_weight": True,
            "weighing_user_id": self.env.user.id,
            "weighing_date": fields.Datetime.now(),
        })
        picking.button_validate()
        self.assertAlmostEqual(line.quantity, 0.980, places=3)

    def test_invoice_uses_delivered_weight(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.product_cheese.id,
                "product_uom_qty": 2,
                "price_unit": 8000.0,
                "price_per_weight": 8000.0,
            })],
        })
        order.action_confirm()
        picking = order.picking_ids[:1]
        picking.action_assign()
        line = picking.move_ids[0].move_line_ids[:1]
        line.write({
            "recorded_weight": 1.234,
            "has_recorded_weight": True,
            "weighing_user_id": self.env.user.id,
            "weighing_date": fields.Datetime.now(),
        })
        picking.button_validate()
        self.assertAlmostEqual(
            order.order_line.total_delivered_weight, 1.234, places=3
        )
        invoice = order._create_invoices()
        inv_line = invoice.invoice_line_ids[:1]
        self.assertAlmostEqual(inv_line.quantity, 1.234, places=3)
        self.assertEqual(inv_line.product_uom_id, self.kg_uom)
        self.assertAlmostEqual(inv_line.price_unit, 8000.0, places=2)
        self.assertAlmostEqual(inv_line.price_subtotal, 1.234 * 8000.0, places=0)

    def test_pricelist_does_not_break_plain_products(self):
        """A pricelist with weighed items must keep working for plain products."""
        pricelist = self.env["product.pricelist"].create({
            "name": "Test PL",
            "item_ids": [(0, 0, {
                "applied_on": "1_product",
                "product_tmpl_id": self.product_cheese.product_tmpl_id.id,
                "compute_price": "fixed",
                "is_weighed_price": True,
                "price_per_weight": 9000.0,
            })],
        })
        plain_price = pricelist._get_product_price(self.product_plain, 1.0)
        self.assertAlmostEqual(plain_price, 25.0, places=2)
        weighed_price = pricelist._get_product_price(self.product_cheese, 1.0)
        self.assertAlmostEqual(weighed_price, 9000.0, places=2)

    def test_pricelist_discount_mode(self):
        pricelist = self.env["product.pricelist"].create({
            "name": "PL Discount",
            "item_ids": [(0, 0, {
                "applied_on": "3_global",
                "compute_price": "discount",
                "base": "list_price",
                "is_weighed_price": True,
                "price_discount": 10.0,
            })],
        })
        price = pricelist._get_product_price(self.product_cheese, 1.0)
        self.assertAlmostEqual(price, 9.0, places=2)

    def test_pricelist_formula_mode(self):
        pricelist = self.env["product.pricelist"].create({
            "name": "PL Formula",
            "item_ids": [(0, 0, {
                "applied_on": "3_global",
                "compute_price": "formula",
                "base": "standard_price",
                "is_weighed_price": True,
                "price_discount": 50.0,
            })],
        })
        price = pricelist._get_product_price(self.product_cheese, 1.0)
        self.assertAlmostEqual(price, 6.0, places=2)

    def test_lock_concurrent_weighing(self):
        picking = self._make_outgoing_picking(self.product_cheese, 2.0)
        move = picking.move_ids[0]
        other_user = self.env["res.users"].create({
            "name": "Other",
            "login": "other_weigher",
        })
        move.with_user(other_user).action_lock_weighing_operation()
        with self.assertRaises(UserError):
            move.action_lock_weighing_operation()
