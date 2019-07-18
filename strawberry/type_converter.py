from collections.abc import AsyncGenerator

from graphql import (
    GraphQLBoolean,
    GraphQLFloat,
    GraphQLID,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLString,
    GraphQLUnionType,
)

from .scalars import ID
from .utils.typing import is_union


REGISTRY = {
    str: GraphQLString,
    int: GraphQLInt,
    float: GraphQLFloat,
    bool: GraphQLBoolean,
    ID: GraphQLID,
}


# TODO: make so that we don't pass force optional
# we use that when trying to get the type for a
# option field (which can either be a scalar or an object type)
def get_graphql_type_for_annotation(
    annotation, field_name: str, force_optional: bool = False
):
    # TODO: this might lead to issues with types that have a field value
    is_field_optional = force_optional

    if hasattr(annotation, "field"):
        graphql_type = annotation.field
    else:
        annotation_name = getattr(annotation, "_name", None)

        if annotation_name == "List":
            list_of_type = get_graphql_type_for_annotation(
                annotation.__args__[0], field_name
            )

            return GraphQLList(list_of_type)

        annotation_origin = getattr(annotation, "__origin__", None)

        if annotation_origin == AsyncGenerator:
            # async generators are used in subscription, we only need the yield type
            # https://docs.python.org/3/library/typing.html#typing.AsyncGenerator
            return get_graphql_type_for_annotation(annotation.__args__[0], field_name)

        elif is_union(annotation):
            types = annotation.__args__
            name = field_name or getattr(annotation, "_name", None)
            non_none_types = [x for x in types if x != None.__class__]  # noqa:E721

            # optionals are represented as Union[type, None]
            if len(non_none_types) == 1:
                is_field_optional = True
                graphql_type = get_graphql_type_for_annotation(
                    non_none_types[0], name, force_optional=True
                )
            else:
                is_field_optional = None.__class__ in types

                # TODO: union types don't work with scalar types
                # so we want to return a nice error
                # also we want to make sure we have been passed
                # strawberry types
                def _resolve_type(self, value, _type):
                    return self.field

                graphql_type = GraphQLUnionType(
                    name, [type.field for type in types]
                )
                graphql_type.resolve_type =_resolve_type
        else:
            graphql_type = REGISTRY.get(annotation)

    if not graphql_type:
        raise ValueError(f"Unable to get GraphQL type for {annotation}")

    if is_field_optional:
        return graphql_type

    return GraphQLNonNull(graphql_type)
