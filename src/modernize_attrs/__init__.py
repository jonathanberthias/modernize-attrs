from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
import libcst as cst

def extract_dataclasses(tree: cst.Module) -> Iterator[cst.ClassDef]:
    for node in tree.body:
        if isinstance(node, cst.ClassDef):
            if node.decorators[0].decorator.value == "dataclass":
                yield node


@dataclass(frozen=True)
class Field:
    name: str
    type_or_annotation: cst.CSTNode | None
    default: cst.BaseExpression | None
    default_factory: cst.BaseExpression | None


class DataclassKind(Enum):
    DATACLASS = "dataclass"


@dataclass(frozen=True)
class ClassWithData:
    name: str
    kind: DataclassKind
    arguments: dict[str, bool | cst.BaseExpression]
    fields: list[Field]



def normalize_dataclass(classdef: cst.ClassDef) -> ClassWithData:
    name = classdef.name.value
    kind = classdef.decorators[0]
    fields: list[Field] = []
    for statement in classdef.body.body:
        if isinstance(statement, cst.SimpleStatementLine):
            for node in statement.body:
                if isinstance(node, cst.AnnAssign):
                    target = node.target
                    if not isinstance(target, cst.Name):
                        raise ValueError(f"Only simple names are supported as targets, got: {target}")
                    field_name = target.value
                    field_type = node.annotation
                    default = node.value
                    fields.append(Field(name=field_name, type_or_annotation=field_type, default=default, default_factory=None))
        if isinstance(node, cst.Assign):
            target = node.targets[0]
            if isinstance(target, cst.Name):
                field_name = target.value
                field_type = node.value
                fields.append(Field(name=field_name, type_or_annotation=field_type, default=None, default_factory=None))
    return ClassWithData(name=name, kind=DataclassKind.DATACLASS, arguments={}, fields=fields)



def main() -> None:
    from textwrap import dedent
    test_str = dedent("""
    from dataclasses import dataclass, field

    @dataclass
    class MyClass:
        x: int
        y: str = "hello"
        z: float = field(default=3.14)
    """)
    exec(test_str, {})
    tree = cst.parse_module(test_str)
    # print(tree)
    for classdef in extract_dataclasses(tree):
        print("Found dataclass")
        print(classdef)
        print(normalize_dataclass(classdef))


if __name__ == "__main__":
    main()
