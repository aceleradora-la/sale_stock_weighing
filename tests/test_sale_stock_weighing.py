from odoo.tests import tagged, TransactionCase
from odoo import fields


@tagged("post_install", "-at_install")
class TestSaleStockWeighing(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kg_uom = cls.env.ref("uom.product_uom_kgm")
        cls.unit_uom = cls.env.ref("uom.product_uom_unit")
        cls.weight_category = cls.env.ref("uom.product_uom_categ_kgm")

        cls.product_cheese = cls.env["product.product"].create({
            "name": "Cheese Feta Bar",
            "type": "product",
            "is_weighed_product": True,
            "uom_id": cls.unit_uom.id,
            "uom_po_id": cls.unit_uom.id,
            "weighing_uom_id": cls.kg_uom.id,
            "weight": 0.5,
            "list_price": 10.0,
        })

        cls.partner = cls.env["res.partner"].create({
            "name": "Test Customer",
        })

        cls.picking_type_out = cls.env.ref("stock.picking_type_out")
        cls.picking_type_out.write({
            "weighing_operations": True,
            "print_weighing_label": False,
        })

        cls.route_mto = cls.env.ref("stock.route_warehouse0_mto")
        cls.route_mto.active = True
        cls.product_cheese.route_ids = [(4, cls.route_mto.id)]

    def test_01_product_config(self):
        self.assertTrue(self.product_cheese.is_weighed_product)
        self.assertEqual(self.product_cheese.weighing_uom_id, self.kg_uom)
        self.assertEqual(self.product_cheese.weight, 0.5)

    def test_02_sale_order_weighing_fields(self):
        sale_order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.product_cheese.id,
                "product_uom_qty": 2,
                "price_unit": 10.0,
                "price_per_weight": 10.0,
            })],
        })
        line = sale_order.order_line[0]
        self.assertEqual(line.price_per_weight, 10.0)
        self.assertAlmostEqual(line.total_planned_weight, 1.0, places=2)

    def test_03_weighing_mixin_has_weight(self):
        picking_type_in = self.env.ref("stock.picking_type_in")
        location_supplier = self.env.ref("stock.stock_location_suppliers")
        location_stock = self.env.ref("stock.stock_location_stock")

        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type_in.id,
            "location_id": location_supplier.id,
            "location_dest_id": location_stock.id,
            "partner_id": self.partner.id,
            "move_ids": [(0, 0, {
                "name": "Receive cheese",
                "product_id": self.product_cheese.id,
                "product_uom": self.kg_uom.id,
                "product_uom_qty": 5.0,
                "location_id": location_supplier.id,
                "location_dest_id": location_stock.id,
            })],
        })
        picking.action_confirm()
        move = picking.move_ids[0]
        self.assertTrue(move.has_weight)

    def test_04_weighing_wizard_record(self):
        location_stock = self.env.ref("stock.stock_location_stock")
        location_customer = self.env.ref("stock.stock_location_customers")

        self.env["stock.quant"].create({
            "product_id": self.product_cheese.id,
            "location_id": location_stock.id,
            "quantity": 5.0,
        })

        picking = self.env["stock.picking"].create({
            "picking_type_id": self.picking_type_out.id,
            "location_id": location_stock.id,
            "location_dest_id": location_customer.id,
            "partner_id": self.partner.id,
            "move_ids": [(0, 0, {
                "name": "Deliver cheese",
                "product_id": self.product_cheese.id,
                "product_uom": self.kg_uom.id,
                "product_uom_qty": 2.0,
                "location_id": location_stock.id,
                "location_dest_id": location_customer.id,
            })],
        })
        picking.action_assign()
        move = picking.move_ids[0]
        self.assertTrue(move.has_weight)
        move_line = move.move_line_ids[0]

        move_line.recorded_weight = 0.980
        move_line.has_recorded_weight = True
        move_line.weighing_user_id = self.env.user
        move_line.weighing_date = fields.Datetime.now()

        picking.button_validate()
        self.assertAlmostEqual(move_line.quantity, 0.980, places=3)
