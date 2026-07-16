from . import models
from . import wizards


def post_init_hook(env):
    """Al instalar el módulo, inicializa group_use_weighing para todos los usuarios.
    Como use_stock_weighing es True por defecto para todas las empresas,
    todos los usuarios internos activos deben quedar en el grupo."""
    companies = env["res.company"].search([])
    companies._sync_weighing_group()
    companies._sync_weighing_picking_types()
