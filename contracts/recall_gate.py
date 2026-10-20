# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Optional consumer proving that RecallCircuit makes onchain permissions meaningful."""
from genlayer import *

@gl.contract_interface
class IRecallCircuit:
    class View:
        def is_release_allowed(self, aid: u256) -> bool: ...
        def get_asset(self, aid: u256) -> dict: ...

class ReleaseGuard(gl.Contract):
    registry: Address
    authority: Address
    shipment_count: u256

    def __init__(self, registry: Address):
        self.registry = registry
        self.authority = gl.message.sender_address
        self.shipment_count = u256(0)

    @gl.public.write
    def record_release(self, asset_id: u256, recipient: Address) -> u256:
        # Release cannot proceed when the upstream safety verdict is not current.
        if gl.message.sender_address != self.authority:
            raise gl.vm.UserError("shipper only")
        if not IRecallCircuit(self.registry).view().is_release_allowed(asset_id):
            raise gl.vm.UserError("RecallCircuit blocked release")
        self.shipment_count = u256(int(self.shipment_count) + 1)
        return self.shipment_count

    @gl.public.view
    def can_release(self, asset_id: u256) -> bool:
        return IRecallCircuit(self.registry).view().is_release_allowed(asset_id)
