# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

from textwrap import dedent
from typing import Any, Dict

import pytest

from iceberg import schema
from iceberg.expressions.base import Accessor
from iceberg.files import StructProtocol
from iceberg.schema import build_position_accessors
from iceberg.types import (
    BooleanType,
    FloatType,
    IntegerType,
    ListType,
    MapType,
    NestedField,
    StringType,
    StructType,
)


def test_schema_str(table_schema_simple):
    """Test casting a schema to a string"""
    assert str(table_schema_simple) == dedent(
        """\
    table {
      1: foo: required string
      2: bar: optional int
      3: baz: required boolean
    }"""
    )


@pytest.mark.parametrize(
    "schema, expected_repr",
    [
        (
            schema.Schema(NestedField(1, "foo", StringType()), schema_id=1),
            "Schema(fields=(NestedField(field_id=1, name='foo', field_type=StringType(), is_optional=True),), schema_id=1, identifier_field_ids=[])",
        ),
        (
            schema.Schema(
                NestedField(1, "foo", StringType()), NestedField(2, "bar", IntegerType(), is_optional=False), schema_id=1
            ),
            "Schema(fields=(NestedField(field_id=1, name='foo', field_type=StringType(), is_optional=True), NestedField(field_id=2, name='bar', field_type=IntegerType(), is_optional=False)), schema_id=1, identifier_field_ids=[])",
        ),
    ],
)
def test_schema_repr(schema, expected_repr):
    """Test schema representation"""
    assert repr(schema) == expected_repr


def test_schema_raise_on_duplicate_names():
    """Test schema representation"""
    with pytest.raises(ValueError) as exc_info:
        schema.Schema(
            NestedField(field_id=1, name="foo", field_type=StringType(), is_optional=False),
            NestedField(field_id=2, name="bar", field_type=IntegerType(), is_optional=True),
            NestedField(field_id=3, name="baz", field_type=BooleanType(), is_optional=False),
            NestedField(field_id=4, name="baz", field_type=BooleanType(), is_optional=False),
            schema_id=1,
            identifier_field_ids=[1],
        )

    assert "Invalid schema, multiple fields for name baz: 3 and 4" in str(exc_info.value)


def test_schema_index_by_id_visitor(table_schema_nested):
    """Test index_by_id visitor function"""
    index = schema.index_by_id(table_schema_nested)
    assert index == {
        1: NestedField(field_id=1, name="foo", field_type=StringType(), is_optional=False),
        2: NestedField(field_id=2, name="bar", field_type=IntegerType(), is_optional=True),
        3: NestedField(field_id=3, name="baz", field_type=BooleanType(), is_optional=False),
        4: NestedField(
            field_id=4,
            name="qux",
            field_type=ListType(element_id=5, element_type=StringType(), element_is_optional=True),
            is_optional=True,
        ),
        5: NestedField(field_id=5, name="element", field_type=StringType(), is_optional=True),
        6: NestedField(
            field_id=6,
            name="quux",
            field_type=MapType(
                key_id=7,
                key_type=StringType(),
                value_id=8,
                value_type=MapType(
                    key_id=9, key_type=StringType(), value_id=10, value_type=IntegerType(), value_is_optional=True
                ),
                value_is_optional=True,
            ),
            is_optional=True,
        ),
        7: NestedField(field_id=7, name="key", field_type=StringType(), is_optional=False),
        9: NestedField(field_id=9, name="key", field_type=StringType(), is_optional=False),
        8: NestedField(
            field_id=8,
            name="value",
            field_type=MapType(key_id=9, key_type=StringType(), value_id=10, value_type=IntegerType(), value_is_optional=True),
            is_optional=True,
        ),
        10: NestedField(field_id=10, name="value", field_type=IntegerType(), is_optional=True),
        11: NestedField(
            field_id=11,
            name="location",
            field_type=ListType(
                element_id=12,
                element_type=StructType(
                    NestedField(field_id=13, name="latitude", field_type=FloatType(), is_optional=False),
                    NestedField(field_id=14, name="longitude", field_type=FloatType(), is_optional=False),
                ),
                element_is_optional=True,
            ),
            is_optional=True,
        ),
        12: NestedField(
            field_id=12,
            name="element",
            field_type=StructType(
                NestedField(field_id=13, name="latitude", field_type=FloatType(), is_optional=False),
                NestedField(field_id=14, name="longitude", field_type=FloatType(), is_optional=False),
            ),
            is_optional=True,
        ),
        13: NestedField(field_id=13, name="latitude", field_type=FloatType(), is_optional=False),
        14: NestedField(field_id=14, name="longitude", field_type=FloatType(), is_optional=False),
        15: NestedField(
            field_id=15,
            name="person",
            field_type=StructType(
                NestedField(field_id=16, name="name", field_type=StringType(), is_optional=False),
                NestedField(field_id=17, name="age", field_type=IntegerType(), is_optional=True),
            ),
            is_optional=False,
        ),
        16: NestedField(field_id=16, name="name", field_type=StringType(), is_optional=False),
        17: NestedField(field_id=17, name="age", field_type=IntegerType(), is_optional=True),
    }


def test_schema_index_by_name_visitor(table_schema_nested):
    """Test index_by_name visitor function"""
    index = schema.index_by_name(table_schema_nested)
    assert index == {
        "foo": 1,
        "bar": 2,
        "baz": 3,
        "qux": 4,
        "qux.element": 5,
        "quux": 6,
        "quux.key": 7,
        "quux.value": 8,
        "quux.value.key": 9,
        "quux.value.value": 10,
        "location": 11,
        "location.element": 12,
        "location.element.latitude": 13,
        "location.element.longitude": 14,
        "location.latitude": 13,
        "location.longitude": 14,
        "person": 15,
        "person.name": 16,
        "person.age": 17,
    }


def test_schema_find_column_name(table_schema_nested):
    """Test finding a column name using its field ID"""
    assert table_schema_nested.find_column_name(1) == "foo"
    assert table_schema_nested.find_column_name(2) == "bar"
    assert table_schema_nested.find_column_name(3) == "baz"
    assert table_schema_nested.find_column_name(4) == "qux"
    assert table_schema_nested.find_column_name(5) == "qux.element"
    assert table_schema_nested.find_column_name(6) == "quux"
    assert table_schema_nested.find_column_name(7) == "quux.key"
    assert table_schema_nested.find_column_name(8) == "quux.value"
    assert table_schema_nested.find_column_name(9) == "quux.value.key"
    assert table_schema_nested.find_column_name(10) == "quux.value.value"
    assert table_schema_nested.find_column_name(11) == "location"
    assert table_schema_nested.find_column_name(12) == "location.element"
    assert table_schema_nested.find_column_name(13) == "location.element.latitude"
    assert table_schema_nested.find_column_name(14) == "location.element.longitude"


def test_schema_find_column_name_on_id_not_found(table_schema_nested):
    """Test raising an error when a field ID cannot be found"""
    assert table_schema_nested.find_column_name(99) is None


def test_schema_find_column_name_by_id(table_schema_simple):
    """Test finding a column name given its field ID"""
    assert table_schema_simple.find_column_name(1) == "foo"
    assert table_schema_simple.find_column_name(2) == "bar"
    assert table_schema_simple.find_column_name(3) == "baz"


def test_schema_find_field_by_id(table_schema_simple):
    """Test finding a column using its field ID"""
    index = schema.index_by_id(table_schema_simple)

    column1 = index[1]
    assert isinstance(column1, NestedField)
    assert column1.field_id == 1
    assert column1.type == StringType()
    assert column1.is_optional == False

    column2 = index[2]
    assert isinstance(column2, NestedField)
    assert column2.field_id == 2
    assert column2.type == IntegerType()
    assert column2.is_optional == True

    column3 = index[3]
    assert isinstance(column3, NestedField)
    assert column3.field_id == 3
    assert column3.type == BooleanType()
    assert column3.is_optional == False


def test_schema_find_field_by_id_raise_on_unknown_field(table_schema_simple):
    """Test raising when the field ID is not found among columns"""
    index = schema.index_by_id(table_schema_simple)
    with pytest.raises(Exception) as exc_info:
        index[4]
    assert str(exc_info.value) == "4"


def test_schema_find_field_type_by_id(table_schema_simple):
    """Test retrieving a columns' type using its field ID"""
    index = schema.index_by_id(table_schema_simple)
    assert index[1] == NestedField(field_id=1, name="foo", field_type=StringType(), is_optional=False)
    assert index[2] == NestedField(field_id=2, name="bar", field_type=IntegerType(), is_optional=True)
    assert index[3] == NestedField(field_id=3, name="baz", field_type=BooleanType(), is_optional=False)


def test_index_by_id_schema_visitor(table_schema_nested):
    """Test the index_by_id function that uses the IndexById schema visitor"""
    assert schema.index_by_id(table_schema_nested) == {
        1: NestedField(field_id=1, name="foo", field_type=StringType(), is_optional=False),
        2: NestedField(field_id=2, name="bar", field_type=IntegerType(), is_optional=True),
        3: NestedField(field_id=3, name="baz", field_type=BooleanType(), is_optional=False),
        4: NestedField(
            field_id=4,
            name="qux",
            field_type=ListType(element_id=5, element_type=StringType(), element_is_optional=True),
            is_optional=True,
        ),
        5: NestedField(field_id=5, name="element", field_type=StringType(), is_optional=True),
        6: NestedField(
            field_id=6,
            name="quux",
            field_type=MapType(
                key_id=7,
                key_type=StringType(),
                value_id=8,
                value_type=MapType(
                    key_id=9, key_type=StringType(), value_id=10, value_type=IntegerType(), value_is_optional=True
                ),
                value_is_optional=True,
            ),
            is_optional=True,
        ),
        7: NestedField(field_id=7, name="key", field_type=StringType(), is_optional=False),
        8: NestedField(
            field_id=8,
            name="value",
            field_type=MapType(key_id=9, key_type=StringType(), value_id=10, value_type=IntegerType(), value_is_optional=True),
            is_optional=True,
        ),
        9: NestedField(field_id=9, name="key", field_type=StringType(), is_optional=False),
        10: NestedField(field_id=10, name="value", field_type=IntegerType(), is_optional=True),
        11: NestedField(
            field_id=11,
            name="location",
            field_type=ListType(
                element_id=12,
                element_type=StructType(
                    NestedField(field_id=13, name="latitude", field_type=FloatType(), is_optional=False),
                    NestedField(field_id=14, name="longitude", field_type=FloatType(), is_optional=False),
                ),
                element_is_optional=True,
            ),
            is_optional=True,
        ),
        12: NestedField(
            field_id=12,
            name="element",
            field_type=StructType(
                NestedField(field_id=13, name="latitude", field_type=FloatType(), is_optional=False),
                NestedField(field_id=14, name="longitude", field_type=FloatType(), is_optional=False),
            ),
            is_optional=True,
        ),
        13: NestedField(field_id=13, name="latitude", field_type=FloatType(), is_optional=False),
        14: NestedField(field_id=14, name="longitude", field_type=FloatType(), is_optional=False),
        15: NestedField(
            field_id=15,
            name="person",
            field_type=StructType(
                NestedField(field_id=16, name="name", field_type=StringType(), is_optional=False),
                NestedField(field_id=17, name="age", field_type=IntegerType(), is_optional=True),
            ),
            is_optional=False,
        ),
        16: NestedField(field_id=16, name="name", field_type=StringType(), is_optional=False),
        17: NestedField(field_id=17, name="age", field_type=IntegerType(), is_optional=True),
    }


def test_index_by_id_schema_visitor_raise_on_unregistered_type():
    """Test raising a NotImplementedError when an invalid type is provided to the index_by_id function"""
    with pytest.raises(NotImplementedError) as exc_info:
        schema.index_by_id("foo")
    assert "Cannot visit non-type: foo" in str(exc_info.value)


def test_schema_find_field(table_schema_simple):
    """Test finding a field in a schema"""
    assert (
        table_schema_simple.find_field(1)
        == table_schema_simple.find_field("foo")
        == table_schema_simple.find_field("FOO", case_sensitive=False)
        == NestedField(field_id=1, name="foo", field_type=StringType(), is_optional=False)
    )
    assert (
        table_schema_simple.find_field(2)
        == table_schema_simple.find_field("bar")
        == table_schema_simple.find_field("BAR", case_sensitive=False)
        == NestedField(field_id=2, name="bar", field_type=IntegerType(), is_optional=True)
    )
    assert (
        table_schema_simple.find_field(3)
        == table_schema_simple.find_field("baz")
        == table_schema_simple.find_field("BAZ", case_sensitive=False)
        == NestedField(field_id=3, name="baz", field_type=BooleanType(), is_optional=False)
    )


def test_schema_find_type(table_schema_simple):
    """Test finding the type of a column given its field ID"""
    assert (
        table_schema_simple.find_type(1)
        == table_schema_simple.find_type("foo")
        == table_schema_simple.find_type("FOO", case_sensitive=False)
        == StringType()
    )
    assert (
        table_schema_simple.find_type(2)
        == table_schema_simple.find_type("bar")
        == table_schema_simple.find_type("BAR", case_sensitive=False)
        == IntegerType()
    )
    assert (
        table_schema_simple.find_type(3)
        == table_schema_simple.find_type("baz")
        == table_schema_simple.find_type("BAZ", case_sensitive=False)
        == BooleanType()
    )


def test_build_position_accessors(table_schema_nested):
    accessors = build_position_accessors(table_schema_nested)
    assert accessors == {
        1: Accessor(position=0, inner=None),
        2: Accessor(position=1, inner=None),
        3: Accessor(position=2, inner=None),
        4: Accessor(position=3, inner=None),
        6: Accessor(position=4, inner=None),
        11: Accessor(position=5, inner=None),
        16: Accessor(position=6, inner=Accessor(position=0, inner=None)),
        17: Accessor(position=6, inner=Accessor(position=1, inner=None)),
    }


class TestStruct(StructProtocol):
    def __init__(self, pos: Dict[int, Any] = None):
        self._pos: Dict[int, Any] = pos or {}

    def set(self, pos: int, value) -> None:
        pass

    def get(self, pos: int) -> Any:
        return self._pos[pos]


def test_build_position_accessors_with_struct(table_schema_nested):
    accessors = build_position_accessors(table_schema_nested)
    container = TestStruct({6: TestStruct({0: "name"})})
    assert accessors.get(16).get(container) == "name"
