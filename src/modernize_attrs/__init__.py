from typing import Union
import libcst as cst
from libcst import matchers as m
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand
from libcst.codemod.visitors import AddImportsVisitor, RemoveImportsVisitor
from libcst.metadata import QualifiedNameProvider, QualifiedName


class FieldDecoratorCollector(cst.CSTVisitor):
    def __init__(self, decorators):
        self.fields = set()
        self.decorators = set(decorators)
    def visit_FunctionDef(self, node: cst.FunctionDef):
        if node.decorators:
            for dec in node.decorators:
                if (
                    isinstance(dec.decorator, cst.Attribute)
                    and dec.decorator.attr.value in self.decorators
                ):
                    if isinstance(dec.decorator.value, cst.Name):
                        self.fields.add(dec.decorator.value.value)


class ModernizeAttrsCodemod(VisitorBasedCodemodCommand):
    """
    Codemod that converts @attrs.s decorators to @define from attrs package.
    """

    DESCRIPTION = "Converts @attrs.s decorators to @define from attrs"
    METADATA_DEPENDENCIES = (QualifiedNameProvider,)

    def __init__(self, context: CodemodContext) -> None:
        super().__init__(context)
        self.current_class_has_untyped_attr = False
        self.current_class_name = None
        self.in_annotated_assign = False
        self.did_transform = False
        self._decorated_fields = set()

    def _is_attrs_decorator(self, node: cst.Decorator) -> bool:
        # Use LibCST metadata to resolve full name
        qualified_names = self.get_metadata(
            QualifiedNameProvider, node.decorator, set()
        )
        for qn in qualified_names:
            if isinstance(qn, QualifiedName):
                if qn.name in [
                    "attr.s",
                    "attrs.s",
                    "attr.attrs",
                ]:
                    return True
        return False

    def _is_ib_call(self, node: cst.Call) -> bool:
        qualified_names = self.get_metadata(QualifiedNameProvider, node.func, set())
        for qn in qualified_names:
            if isinstance(qn, QualifiedName):
                if qn.name in [
                    "attr.ib",
                    "attrs.ib",
                    "attr.attrib",
                    "attrs.attrib",
                ]:
                    return True
        return False

    def _extract_attr_args(
        self, node: cst.Call
    ) -> tuple[cst.BaseExpression | None, list[cst.Arg]]:
        """Extract type argument and remaining arguments from attr.ib() call."""
        type_arg = None
        remaining_args = []

        if hasattr(node, "args"):
            for arg in node.args:
                if m.matches(arg, m.Arg(keyword=m.Name(value="type"))):
                    type_arg = arg.value
                else:
                    remaining_args.append(arg)

        return type_arg, remaining_args

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        self.in_annotated_assign = True

    def leave_AnnAssign(
        self, original_node: cst.AnnAssign, updated_node: cst.AnnAssign
    ) -> cst.AnnAssign:
        self.in_annotated_assign = False
        if self.current_class_has_untyped_attr or not (
            original_node.value
            and isinstance(original_node.value, cst.Call)
            and self._is_ib_call(original_node.value)
        ):
            return original_node

        self.did_transform = True
        remaining_args = []
        if hasattr(original_node.value, "args"):
            remaining_args = [
                arg
                for arg in original_node.value.args
                if not (arg.keyword and arg.keyword.value == "type")
            ]
        field_name = original_node.target.value if isinstance(original_node.target, cst.Name) else None
        force_field = field_name in self._decorated_fields
        if not remaining_args and not force_field:
            return cst.AnnAssign(
                target=original_node.target,
                annotation=original_node.annotation,
                value=None,
            )
        return updated_node.with_changes(
            value=cst.Call(func=cst.Name(value="field"), args=remaining_args)
        )

    @m.call_if_inside(m.ClassDef())
    def visit_Call(self, node: cst.Call) -> None:
        if self._is_ib_call(node):
            # Don't mark as untyped if we're in an annotated assignment
            if self.in_annotated_assign:
                return
            # Check for type argument
            has_type = any(
                arg.keyword and arg.keyword.value == "type" for arg in node.args
            )
            if not has_type:
                self.current_class_has_untyped_attr = True

    @m.call_if_inside(m.ClassDef())
    def leave_Decorator(
        self, original_node: cst.Decorator, updated_node: cst.Decorator
    ) -> Union[cst.Decorator, cst.RemovalSentinel]:
        if self.current_class_has_untyped_attr:
            return original_node
        if self._is_attrs_decorator(original_node):
            self.did_transform = True
            # Preserve arguments to the decorator, but remove auto_attribs only if True
            if isinstance(original_node.decorator, cst.Call):
                filtered_args = []
                for arg in original_node.decorator.args:
                    if arg.keyword and arg.keyword.value == "auto_attribs":
                        # Only remove if value is True
                        if isinstance(arg.value, cst.Name) and arg.value.value == "True":
                            continue
                    filtered_args.append(arg)
                if filtered_args:
                    return cst.Decorator(
                        decorator=cst.Call(
                            func=cst.Name(value="define"),
                            args=filtered_args
                        )
                    )
                else:
                    return cst.Decorator(decorator=cst.Name(value="define"))
            else:
                return cst.Decorator(decorator=cst.Name(value="define"))
        return updated_node

    def leave_Module(
        self, original_node: cst.Module, updated_node: cst.Module
    ) -> cst.Module:
        AddImportsVisitor.add_needed_import(self.context, "attrs", "define")
        AddImportsVisitor.add_needed_import(self.context, "attrs", "field")
        RemoveImportsVisitor.remove_unused_import(self.context, "attrs", "define")
        RemoveImportsVisitor.remove_unused_import(self.context, "attrs", "field")

        # Remove all forms of old imports
        RemoveImportsVisitor.remove_unused_import(self.context, "attr")
        RemoveImportsVisitor.remove_unused_import(self.context, "attrs")
        RemoveImportsVisitor.remove_unused_import(self.context, "attr", "attrs")
        RemoveImportsVisitor.remove_unused_import(self.context, "attr", "attrib")
        RemoveImportsVisitor.remove_unused_import(self.context, "attr", "ib")
        return updated_node

    @m.call_if_inside(m.ClassDef())
    def leave_Assign(
        self, original_node: cst.Assign, updated_node: cst.Assign
    ) -> Union[cst.Assign, cst.AnnAssign]:
        if self.current_class_has_untyped_attr or not (
            original_node.value
            and isinstance(original_node.value, cst.Call)
            and self._is_ib_call(original_node.value)
        ):
            return original_node

        self.did_transform = True
        type_arg, remaining_args = self._extract_attr_args(original_node.value)
        target = original_node.targets[0].target
        field_name = target.value if isinstance(target, cst.Name) else None
        force_field = field_name in self._decorated_fields
        if type_arg:
            if (
                len(remaining_args) == 1
                and remaining_args[0].keyword
                and remaining_args[0].keyword.value == "default"
                and not force_field
            ):
                return cst.AnnAssign(
                    target=target,
                    annotation=cst.Annotation(annotation=type_arg),
                    value=remaining_args[0].value,
                )
            if not remaining_args and not force_field:
                return cst.AnnAssign(
                    target=target,
                    annotation=cst.Annotation(annotation=type_arg),
                    value=None,
                )
            return cst.AnnAssign(
                target=target,
                annotation=cst.Annotation(annotation=type_arg),
                value=cst.Call(func=cst.Name(value="field"), args=remaining_args),
            )
        if (
            len(remaining_args) == 1
            and remaining_args[0].keyword
            and remaining_args[0].keyword.value == "default"
            and not force_field
        ):
            return cst.Assign(
                targets=[cst.AssignTarget(target=target)],
                value=remaining_args[0].value,
            )
        if remaining_args or force_field:
            return cst.Assign(
                targets=[cst.AssignTarget(target=target)],
                value=cst.Call(func=cst.Name(value="field"), args=remaining_args),
            )
        return cst.Assign(targets=[cst.AssignTarget(target=target)], value=target)

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self.current_class_has_untyped_attr = False
        self.current_class_name = node.name.value
        # Use FieldDecoratorCollector visitor to collect relevant fields
        collector = FieldDecoratorCollector({"validator", "default"})
        node.visit(collector)
        self._decorated_fields = collector.fields

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        if self.current_class_has_untyped_attr:
            print(
                f"Warning: Skipping class {self.current_class_name} because it contains attr.ib() or attrib() without type hints"
            )
            self.did_transform = False
            return original_node
        return updated_node
