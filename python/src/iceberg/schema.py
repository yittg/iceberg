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

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Generic, Iterable, List, Optional, TypeVar

from iceberg.files import StructProtocol

if sys.version_info >= (3, 8):
    from functools import singledispatch  # pragma: no cover
else:
    from singledispatch import singledispatch  # pragma: no cover

from iceberg.types import (
    IcebergType,
    ListType,
    MapType,
    NestedField,
    PrimitiveType,
    StructType,
)

T = TypeVar("T")


class Schema:
    """A table Schema

    Example:
        >>> from iceberg import schema
        >>> from iceberg import types
    """

    def __init__(self, *columns: Iterable[NestedField], schema_id: int, identifier_field_ids: Optional[List[int]] = None):
        self._struct = StructType(*columns)  # type: ignore
        self._schema_id = schema_id
        self._identifier_field_ids = identifier_field_ids or []
        self._name_to_id: Dict[str, int] = index_by_name(self)
        self._name_to_id_lower: Dict[str, int] = {}  # Should be accessed through self._lazy_name_to_id_lower()
        self._id_to_field: Dict[int, NestedField] = {}  # Should be accessed through self._lazy_id_to_field()
        self._id_to_name: Dict[int, str] = {}  # Should be accessed through self._lazy_id_to_name()
        self._id_to_accessor: Dict[int, Accessor] = {}  # Should be accessed through self._lazy_id_to_accessor()

    def __str__(self):
        return "table {\n" + "\n".join(["  " + str(field) for field in self.columns]) + "\n}"

    def __repr__(self):
        return (
            f"Schema(fields={repr(self.columns)}, schema_id={self.schema_id}, identifier_field_ids={self.identifier_field_ids})"
        )

    @property
    def columns(self) -> Iterable[NestedField]:
        """A list of the top-level fields in the underlying struct"""
        return self._struct.fields

    @property
    def schema_id(self) -> int:
        """The ID of this Schema"""
        return self._schema_id

    @property
    def identifier_field_ids(self) -> List[int]:
        return self._identifier_field_ids

    def _lazy_id_to_field(self) -> Dict[int, NestedField]:
        """Returns an index of field ID to NestedField instance

        This is calculated once when called for the first time. Subsequent calls to this method will use a cached index.
        """
        if not self._id_to_field:
            self._id_to_field = index_by_id(self)
        return self._id_to_field

    def _lazy_name_to_id_lower(self) -> Dict[str, int]:
        """Returns an index of lower-case field names to field IDs

        This is calculated once when called for the first time. Subsequent calls to this method will use a cached index.
        """
        if not self._name_to_id_lower:
            self._name_to_id_lower = {name.lower(): field_id for name, field_id in self._name_to_id.items()}
        return self._name_to_id_lower

    def _lazy_id_to_name(self) -> Dict[int, str]:
        """Returns an index of field ID to full name

        This is calculated once when called for the first time. Subsequent calls to this method will use a cached index.
        """
        if not self._id_to_name:
            self._id_to_name = index_name_by_id(self)
        return self._id_to_name

    def _lazy_id_to_accessor(self) -> Dict[int, Accessor]:
        """Returns an index of field ID to accessor

        This is calculated once when called for the first time. Subsequent calls to this method will use a cached index.
        """
        if not self._id_to_accessor:
            self._id_to_accessor = build_position_accessors(self)
        return self._id_to_accessor

    def as_struct(self) -> StructType:
        """Returns the underlying struct"""
        return self._struct

    def find_field(self, name_or_id: str | int, case_sensitive: bool = True) -> NestedField:
        """Find a field using a field name or field ID

        Args:
            name_or_id (str | int): Either a field name or a field ID
            case_sensitive (bool, optional): Whether to perform a case-sensitive lookup using a field name. Defaults to True.

        Returns:
            NestedField: The matched NestedField
        """
        if isinstance(name_or_id, int):
            field = self._lazy_id_to_field().get(name_or_id)
            return field  # type: ignore
        if case_sensitive:
            field_id = self._name_to_id.get(name_or_id)
        else:
            field_id = self._lazy_name_to_id_lower().get(name_or_id.lower())
        return self._lazy_id_to_field().get(field_id)  # type: ignore

    def find_type(self, name_or_id: str | int, case_sensitive: bool = True) -> IcebergType:
        """Find a field type using a field name or field ID

        Args:
            name_or_id (str | int): Either a field name or a field ID
            case_sensitive (bool, optional): Whether to perform a case-sensitive lookup using a field name. Defaults to True.

        Returns:
            NestedField: The type of the matched NestedField
        """
        field = self.find_field(name_or_id=name_or_id, case_sensitive=case_sensitive)
        return field.type  # type: ignore

    def find_column_name(self, column_id: int) -> str:
        """Find a column name given a column ID

        Args:
            column_id (int): The ID of the column

        Returns:
            str: The column name (or None if the column ID cannot be found)
        """
        return self._lazy_id_to_name().get(column_id)  # type: ignore

    def accessor_for_field(self, field_id: int) -> Accessor:
        """Find a schema position accessor given a field ID

        Args:
            field_id (int): The ID of the field

        Returns:
            Accessor: An accessor for the given field ID
        """
        return self._lazy_id_to_accessor().get(field_id)  # type: ignore

    def select(self, names: List[str], case_sensitive: bool = True) -> "Schema":
        """Return a new schema instance pruned to a subset of columns

        Args:
            names (List[str]): A list of column names
            case_sensitive (bool, optional): Whether to perform a case-sensitive lookup for each column name. Defaults to True.

        Returns:
            Schema: A new schema with pruned columns
        """
        if case_sensitive:
            return self._case_sensitive_select(schema=self, names=names)
        return self._case_insensitive_select(schema=self, names=names)

    @classmethod
    def _case_sensitive_select(cls, schema: "Schema", names: List[str]):
        # TODO: Add a PruneColumns schema visitor and use it here
        raise NotImplementedError()

    @classmethod
    def _case_insensitive_select(cls, schema: "Schema", names: List[str]):
        # TODO: Add a PruneColumns schema visitor and use it here
        raise NotImplementedError()


class SchemaVisitor(Generic[T], ABC):
    def before_field(self, field: NestedField) -> None:
        """Override this method to perform an action immediately before visiting a field"""

    def after_field(self, field: NestedField) -> None:
        """Override this method to perform an action immediately after visiting a field"""

    def before_list_element(self, element: NestedField) -> None:
        """Override this method to perform an action immediately before visiting an element within a ListType"""
        self.before_field(element)

    def after_list_element(self, element: NestedField) -> None:
        """Override this method to perform an action immediately after visiting an element within a ListType"""
        self.after_field(element)

    def before_map_key(self, key: NestedField) -> None:
        """Override this method to perform an action immediately before visiting a key within a MapType"""
        self.before_field(key)

    def after_map_key(self, key: NestedField) -> None:
        """Override this method to perform an action immediately after visiting a key within a MapType"""
        self.after_field(key)

    def before_map_value(self, value: NestedField) -> None:
        """Override this method to perform an action immediately before visiting a value within a MapType"""
        self.before_field(value)

    def after_map_value(self, value: NestedField) -> None:
        """Override this method to perform an action immediately after visiting a value within a MapType"""
        self.after_field(value)

    @abstractmethod
    def schema(self, schema: Schema, struct_result: T) -> T:
        """Visit a Schema"""
        ...  # pragma: no cover

    @abstractmethod
    def struct(self, struct: StructType, field_results: List[T]) -> T:
        """Visit a StructType"""
        ...  # pragma: no cover

    @abstractmethod
    def field(self, field: NestedField, field_result: T) -> T:
        """Visit a NestedField"""
        ...  # pragma: no cover

    @abstractmethod
    def list(self, list_type: ListType, element_result: T) -> T:
        """Visit a ListType"""
        ...  # pragma: no cover

    @abstractmethod
    def map(self, map_type: MapType, key_result: T, value_result: T) -> T:
        """Visit a MapType"""
        ...  # pragma: no cover

    @abstractmethod
    def primitive(self, primitive: PrimitiveType) -> T:
        """Visit a PrimitiveType"""
        ...  # pragma: no cover


@dataclass(init=True, eq=True, frozen=True)
class Accessor:
    """An accessor for a specific position in a container that implements the StructProtocol"""

    position: int
    inner: Optional["Accessor"] = None

    def __str__(self):
        return f"Accessor(position={self.position},inner={self.inner})"

    def __repr__(self):
        return self.__str__()

    def get(self, container: StructProtocol) -> Any:
        """Returns the value at self.position in `container`

        Args:
            container(StructProtocol): A container to access at position `self.position`

        Returns:
            Any: The value at position `self.position` in the container
        """
        pos = self.position
        val = container.get(pos)
        inner = self
        while inner.inner:
            inner = inner.inner
            val = val.get(inner.position)

        return val


@singledispatch
def visit(obj, visitor: SchemaVisitor[T]) -> T:
    """A generic function for applying a schema visitor to any point within a schema

    The function traverses the schema in post-order fashion

    Args:
        obj(Schema | IcebergType): An instance of a Schema or an IcebergType
        visitor (SchemaVisitor[T]): An instance of an implementation of the generic SchemaVisitor base class

    Raises:
        NotImplementedError: If attempting to visit an unrecognized object type
    """
    raise NotImplementedError("Cannot visit non-type: %s" % obj)


@visit.register(Schema)
def _(obj: Schema, visitor: SchemaVisitor[T]) -> T:
    """Visit a Schema with a concrete SchemaVisitor"""
    return visitor.schema(obj, visit(obj.as_struct(), visitor))


@visit.register(StructType)
def _(obj: StructType, visitor: SchemaVisitor[T]) -> T:
    """Visit a StructType with a concrete SchemaVisitor"""
    results = []

    for field in obj.fields:
        visitor.before_field(field)
        result = visit(field.type, visitor)
        visitor.after_field(field)
        results.append(visitor.field(field, result))

    return visitor.struct(obj, results)


@visit.register(ListType)
def _(obj: ListType, visitor: SchemaVisitor[T]) -> T:
    """Visit a ListType with a concrete SchemaVisitor"""

    visitor.before_list_element(obj.element)
    result = visit(obj.element.type, visitor)
    visitor.after_list_element(obj.element)

    return visitor.list(obj, result)


@visit.register(MapType)
def _(obj: MapType, visitor: SchemaVisitor[T]) -> T:
    """Visit a MapType with a concrete SchemaVisitor"""
    visitor.before_map_key(obj.key)
    key_result = visit(obj.key.type, visitor)
    visitor.after_map_key(obj.key)

    visitor.before_map_value(obj.value)
    value_result = visit(obj.value.type, visitor)
    visitor.after_list_element(obj.value)

    return visitor.map(obj, key_result, value_result)


@visit.register(PrimitiveType)
def _(obj: PrimitiveType, visitor: SchemaVisitor[T]) -> T:
    """Visit a PrimitiveType with a concrete SchemaVisitor"""
    return visitor.primitive(obj)


class _IndexById(SchemaVisitor[Dict[int, NestedField]]):
    """A schema visitor for generating a field ID to NestedField index"""

    def __init__(self) -> None:
        self._index: Dict[int, NestedField] = {}

    def schema(self, schema: Schema, result) -> Dict[int, NestedField]:
        return self._index

    def struct(self, struct: StructType, result) -> Dict[int, NestedField]:
        return self._index

    def field(self, field: NestedField, result) -> Dict[int, NestedField]:
        """Add the field ID to the index"""
        self._index[field.field_id] = field
        return self._index

    def list(self, list_type: ListType, result) -> Dict[int, NestedField]:
        """Add the list element ID to the index"""
        self._index[list_type.element.field_id] = list_type.element
        return self._index

    def map(self, map_type: MapType, key_result, value_result) -> Dict[int, NestedField]:
        """Add the key ID and value ID as individual items in the index"""
        self._index[map_type.key.field_id] = map_type.key
        self._index[map_type.value.field_id] = map_type.value
        return self._index

    def primitive(self, primitive) -> Dict[int, NestedField]:
        return self._index


def index_by_id(schema_or_type) -> Dict[int, NestedField]:
    """Generate an index of field IDs to NestedField instances

    Args:
        schema_or_type (Schema | IcebergType): A schema or type to index

    Returns:
        Dict[int, NestedField]: An index of field IDs to NestedField instances
    """
    return visit(schema_or_type, _IndexById())


class _IndexByName(SchemaVisitor[Dict[str, int]]):
    """A schema visitor for generating a field name to field ID index"""

    def __init__(self) -> None:
        self._index: Dict[str, int] = {}
        self._short_name_to_id: Dict[str, int] = {}
        self._combined_index: Dict[str, int] = {}
        self._field_names: List[str] = []
        self._short_field_names: List[str] = []

    def before_list_element(self, element: NestedField) -> None:
        """Short field names omit element when the element is a StructType"""
        if not isinstance(element.type, StructType):
            self._short_field_names.append(element.name)
        self._field_names.append(element.name)

    def after_list_element(self, element: NestedField) -> None:
        if not isinstance(element.type, StructType):
            self._short_field_names.pop()
        self._field_names.pop()

    def before_field(self, field: NestedField) -> None:
        """Store the field name"""
        self._field_names.append(field.name)
        self._short_field_names.append(field.name)

    def after_field(self, field: NestedField) -> None:
        """Remove the last field name stored"""
        self._field_names.pop()
        self._short_field_names.pop()

    def schema(self, schema: Schema, struct_result: Dict[str, int]) -> Dict[str, int]:
        return self._index

    def struct(self, struct: StructType, struct_result: List[Dict[str, int]]) -> Dict[str, int]:
        return self._index

    def field(self, field: NestedField, struct_result: Dict[str, int]) -> Dict[str, int]:
        """Add the field name to the index"""
        self._add_field(field.name, field.field_id)
        return self._index

    def list(self, list_type: ListType, struct_result: Dict[str, int]) -> Dict[str, int]:
        """Add the list element name to the index"""
        self._add_field(list_type.element.name, list_type.element.field_id)
        return self._index

    def map(self, map_type: MapType, key_result: Dict[str, int], value_result: Dict[str, int]) -> Dict[str, int]:
        """Add the key name and value name as individual items in the index"""
        self._add_field(map_type.key.name, map_type.key.field_id)
        self._add_field(map_type.value.name, map_type.value.field_id)
        return self._index

    def _add_field(self, name: str, field_id: int):
        """Add a field name to the index, mapping its full name to its field ID

        Args:
            name (str): The field name
            field_id (int): The field ID

        Raises:
            ValueError: If the field name is already contained in the index
        """
        full_name = name

        if self._field_names:
            full_name = ".".join([".".join(self._field_names), name])

        if full_name in self._index:
            raise ValueError(f"Invalid schema, multiple fields for name {full_name}: {self._index[full_name]} and {field_id}")
        self._index[full_name] = field_id

        if self._short_field_names:
            short_name = ".".join([".".join(self._short_field_names), name])
            self._short_name_to_id[short_name] = field_id

    def primitive(self, primitive) -> Dict[str, int]:
        return self._index

    def by_name(self) -> Dict[str, int]:
        """Returns an index of combined full and short names

        Note: Only short names that do not conflict with full names are included.
        """
        combined_index = self._short_name_to_id.copy()
        combined_index.update(self._index)
        return combined_index

    def by_id(self) -> Dict[int, str]:
        """Returns an index of ID to full names"""
        id_to_full_name = dict([(value, key) for key, value in self._index.items()])
        return id_to_full_name


def index_by_name(schema_or_type: Schema | IcebergType) -> Dict[str, int]:
    """Generate an index of field names to field IDs

    Args:
        schema_or_type (Schema | IcebergType): A schema or type to index

    Returns:
        Dict[str, int]: An index of field names to field IDs
    """
    indexer = _IndexByName()
    visit(schema_or_type, indexer)
    return indexer.by_name()


def index_name_by_id(schema_or_type: Schema | IcebergType) -> Dict[int, str]:
    """Generate an index of field IDs full field names

    Args:
        schema_or_type (Schema | IcebergType): A schema or type to index

    Returns:
        Dict[str, int]: An index of field IDs to full names
    """
    indexer = _IndexByName()
    visit(schema_or_type, indexer)
    return indexer.by_id()


Position = int


class _BuildPositionAccessors(SchemaVisitor[Dict[Position, Accessor]]):
    """A schema visitor for generating a field ID to accessor index

    Example:
        >>> from iceberg.schema import Schema
        >>> from iceberg.types import *
        >>> schema = Schema(
        ...     NestedField(field_id=2, name="id", field_type=IntegerType(), is_optional=False),
        ...     NestedField(field_id=1, name="data", field_type=StringType(), is_optional=True),
        ...     NestedField(
        ...         field_id=3,
        ...         name="location",
        ...         field_type=StructType(
        ...             NestedField(field_id=5, name="latitude", field_type=FloatType(), is_optional=False),
        ...             NestedField(field_id=6, name="longitude", field_type=FloatType(), is_optional=False),
        ...         ),
        ...         is_optional=True,
        ...     ),
        ...     schema_id=1,
        ...     identifier_field_ids=[1],
        ... )
        >>> result = build_position_accessors(schema)
        >>> expected = {
        ...     2: Accessor(position=0, inner=None),
        ...     1: Accessor(position=1, inner=None),
        ...     5: Accessor(position=2, inner=Accessor(position=0, inner=None)),
        ...     6: Accessor(position=2, inner=Accessor(position=1, inner=None))
        ... }
        >>> result == expected
        True
    """

    @staticmethod
    def _wrap_leaves(result: Dict[Position, Accessor], position: Position = 0) -> Dict[Position, Accessor]:
        return {field_id: Accessor(position, inner=inner) for field_id, inner in result.items()}

    def schema(self, schema: Schema, result: Dict[Position, Accessor]) -> Dict[Position, Accessor]:
        return result

    def struct(self, struct: StructType, field_results: List[Dict[Position, Accessor]]) -> Dict[Position, Accessor]:
        result = {}

        for position, field in enumerate(struct.fields):
            if field_results[position]:
                for inner_field_id, acc in field_results[position].items():
                    result[inner_field_id] = Accessor(position, inner=acc)
            else:
                result[field.field_id] = Accessor(position)

        return result

    def field(self, field: NestedField, result: Dict[Position, Accessor]) -> Dict[Position, Accessor]:
        return result

    def list(self, list_type: ListType, result: Dict[Position, Accessor]) -> Dict[Position, Accessor]:
        return {}

    def map(
        self, map_type: MapType, key_result: Dict[Position, Accessor], value_result: Dict[Position, Accessor]
    ) -> Dict[Position, Accessor]:
        return {}

    def primitive(self, primitive: PrimitiveType) -> Dict[Position, Accessor]:
        return {}


def build_position_accessors(schema_or_type: Schema | IcebergType) -> Dict[int, Accessor]:
    """Generate an index of field IDs to schema position accessors

    Args:
        schema_or_type (Schema | IcebergType): A schema or type to index

    Returns:
        Dict[int, Accessor]: An index of field IDs to accessors
    """
    return visit(schema_or_type, _BuildPositionAccessors())
