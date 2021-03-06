import pytest
from networkx import Graph
from eth_utils import to_canonical_address

from raiden.storage.serialize import JSONSerializer, RaidenJSONDecoder
from raiden.utils import serialization
from raiden.transfer.merkle_tree import compute_layers
from raiden.transfer.state import EMPTY_MERKLE_TREE


class MockObject(object):
    """ Used for testing JSON encoding/decoding """
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def to_dict(self):
        return {
            key: value
            for key, value in self.__dict__.items()
        }

    @classmethod
    def from_dict(cls, data):
        obj = cls()
        for key, value in data.items():
            setattr(obj, key, value)
        return obj

    def __eq__(self, other):
        if not isinstance(other, MockObject):
            return False
        for key, value in self.__dict__.items():
            if key not in other.__dict__ or value != other.__dict__[key]:
                return False

        return True


def test_object_custom_serialization():
    # Simple encode/decode
    original_obj = MockObject(attr1="Hello", attr2="World")
    decoded_obj = JSONSerializer.deserialize(
        JSONSerializer.serialize(original_obj),
    )

    assert original_obj == decoded_obj

    # Encode/Decode with embedded objects
    embedded_obj = MockObject(amount=1, identifier='123')
    original_obj = MockObject(embedded=embedded_obj)
    decoded_obj = JSONSerializer.deserialize(
        JSONSerializer.serialize(original_obj),
    )

    assert original_obj == decoded_obj
    assert decoded_obj.embedded.amount == 1
    assert decoded_obj.embedded.identifier == '123'


def test_ref_cache():
    import_path = f'{MockObject.__module__}.{MockObject.__class__.__name__}'
    ref_cache = serialization.ReferenceCache()

    embedded_A = MockObject(channel_id='0x3DE6B821E4fb4599653BF76FF60dC5FaF2e92De8')
    A = MockObject(attr1=10, attr2='123', embedded=embedded_A)

    # A is not cached yet
    assert ref_cache.get(import_path, A) is None

    ref_cache.add(import_path, A)
    assert len(ref_cache._cache[import_path]) == 1

    # Object should not be added again
    ref_cache.add(import_path, A)
    assert len(ref_cache._cache[import_path]) == 1

    # Create an exact replica of A
    embedded_B = MockObject(channel_id='0x3DE6B821E4fb4599653BF76FF60dC5FaF2e92De8')
    B = MockObject(attr1=10, attr2='123', embedded=embedded_B)

    assert A == B  # Both objects are equal because their attributes are equal

    # get() should return A as B is exactly the same, but we want to have exactly
    # one instance of each class where all the attributes match.
    assert id(A) == id(ref_cache.get(import_path, B))


def test_decode_with_ref_cache():
    embedded_A = MockObject(channel_id='0x3DE6B821E4fb4599653BF76FF60dC5FaF2e92De8')
    A = MockObject(attr1=10, attr2='123', embedded=embedded_A)

    decoded_A = JSONSerializer.deserialize(
        JSONSerializer.serialize(A),
    )

    assert A == decoded_A

    # Create an exact replica of A
    embedded_B = MockObject(channel_id='0x3DE6B821E4fb4599653BF76FF60dC5FaF2e92De8')
    B = MockObject(attr1=10, attr2='123', embedded=embedded_B)

    decoded_B = JSONSerializer.deserialize(
        JSONSerializer.serialize(B),
    )

    assert B == decoded_B
    assert id(B) != id(decoded_B)
    # Make sure that the original decoded A
    # is returned
    assert id(decoded_A) == id(decoded_B)

    # Make sure no object is cached
    RaidenJSONDecoder.cache_object_references = False
    RaidenJSONDecoder.ref_cache.clear()

    # Decode some object
    decoded_B = JSONSerializer.deserialize(
        JSONSerializer.serialize(B),
    )

    for _, cache_entries in RaidenJSONDecoder.ref_cache._cache.items():
        assert len(cache_entries) == 0


def test_decode_with_unknown_type():
    test_str = """
{
    "_type": "some.non.existent.package",
    "attr1": "test"
}
"""
    with pytest.raises(TypeError) as m:
        JSONSerializer.deserialize(test_str)
        assert str(m) == 'Module some.non.existent.package does not exist'

    test_str = """
{
    "_type": "raiden.tests.unit.test_serialization.NonExistentClass",
    "attr1": "test"
}
"""
    with pytest.raises(TypeError) as m:
        JSONSerializer.deserialize(test_str)
        assert str(m) == 'raiden.tests.unit.test_serialization.NonExistentClass'


def test_serialization_networkx_graph():
    p1 = to_canonical_address('0x5522070585a1a275631ba69c444ac0451AA9Fe4C')
    p2 = to_canonical_address('0x5522070585a1a275631ba69c444ac0451AA9Fe4D')
    p3 = to_canonical_address('0x5522070585a1a275631ba69c444ac0451AA9Fe4E')
    p4 = to_canonical_address('0x5522070585a1a275631ba69c444ac0451AA9Fe4F')

    e = [(p1, p2), (p2, p3), (p3, p4)]
    graph = Graph(e)

    data = serialization.serialize_networkx_graph(graph)
    restored_graph = serialization.deserialize_networkx_graph(data)

    assert graph.edges == restored_graph.edges


def test_serialization_participants_tuple():
    participants = (
        to_canonical_address('0x5522070585a1a275631ba69c444ac0451AA9Fe4C'),
        to_canonical_address('0xEF4f7c9962d8bAa8E268B72EC6DD4BDf09C84397'),
    )

    data = serialization.serialize_participants_tuple(participants)
    restored = serialization.deserialize_participants_tuple(data)

    assert participants == restored


def test_serialization_merkletree_layers():
    hash_0 = b'a' * 32
    hash_1 = b'b' * 32

    leaves = [hash_0, hash_1]
    layers = compute_layers(leaves)

    data = serialization.serialize_merkletree_layers(layers)
    restored = serialization.deserialize_merkletree_layers(data)

    assert layers == restored


def test_serialization_merkletree_layers_empty():
    tree = EMPTY_MERKLE_TREE

    data = serialization.serialize_merkletree_layers(tree.layers)
    restored = serialization.deserialize_merkletree_layers(data)

    assert tree.layers == restored
