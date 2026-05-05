import pytest
from valichord_attestation.adapters.base import AdapterBase
from valichord_attestation.adapters.inspect_evals_stub import InspectEvalsAdapter


def test_inspect_evals_adapter_is_subclass_of_base():
    assert issubclass(InspectEvalsAdapter, AdapterBase)


def test_inspect_evals_adapter_raises_not_implemented():
    adapter = InspectEvalsAdapter()
    with pytest.raises(NotImplementedError):
        adapter.to_bundle({}, [])


def test_not_implemented_message_mentions_deferral():
    adapter = InspectEvalsAdapter()
    with pytest.raises(NotImplementedError, match="deferred"):
        adapter.to_bundle({}, [])
