# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Optional consumer proving that RecallCircuit's gate is enforceable cross-contract.

Points at a deployed RecallCircuit (contracts/recall_circuit.py) and refuses to
record a release unless that contract's own can_release(product_id) is true at
call time. This is a voluntary integration: nothing stops a shipper from using
a different contract entirely, or none at all -- see docs/STATE_MACHINE.md.
"""
from genlayer import *

@gl.contract_interface
class IRecallCircuit:
    class View:
        def can_release(self, product_id: u256) -> bool: ...
        def get_product(self, product_id: u256) -> dict: ...

class ReleaseGuard(gl.Contract):
    registry: Address
    authority: Address
    shipment_count: u256

    def __init__(self, registry: Address):
        self.registry = registry
        self.authority = gl.message.sender_address
        self.shipment_count = u256(0)

    @gl.public.write
    def record_release(self, product_id: u256, recipient: Address) -> u256:
        # Release cannot proceed when the upstream safety verdict is not current.
        if gl.message.sender_address != self.authority:
            raise gl.vm.UserError("shipper only")
        if not IRecallCircuit(self.registry).view().can_release(product_id):
            raise gl.vm.UserError("RecallCircuit blocked release")
        self.shipment_count = u256(int(self.shipment_count) + 1)
        return self.shipment_count

    @gl.public.view
    def can_release(self, product_id: u256) -> bool:
        return IRecallCircuit(self.registry).view().can_release(product_id)
