from typing import Union
import libcst as cst
from libcst import matchers as m
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand
from libcst.codemod.visitors import AddImportsVisitor, RemoveImportsVisitor, GatherImportsVisitor
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

    def _parse_field_args(self, args):
        """Parse attr.ib/attrib args into factory/default/other buckets."""
        factory_func = None
        factory_value = None
        other_args = []
        simple_default = None
        default_arg = None
        for arg in args:
            if arg.keyword and arg.keyword.value == "type":
                continue
            if arg.keyword and arg.keyword.value == "default":
                default_arg = arg.value
                # Detect Factory
                if (
                    isinstance(arg.value, cst.Call)
                    and (
                        (isinstance(arg.value.func, cst.Attribute) and arg.value.func.attr.value == "Factory")
                        or (isinstance(arg.value.func, cst.Name) and arg.value.func.value == "Factory")
                    )
                ):
                    factory_func = arg.value.func
                    if arg.value.args:
                        factory_value = arg.value.args[0].value
                    continue
                else:
                    simple_default = arg.value
                    continue
            other_args.append(arg)
        return factory_func, factory_value, simple_default, default_arg, other_args

    def _build_field_value(self, *, target, annotation=None, factory_func=None, factory_value=None, simple_default=None, default_arg=None, other_args=None, force_field=False):
        """Build the correct CST node for the field value."""
        other_args = other_args or []
        # AnnAssign (with annotation)
        if annotation is not None:
            if simple_default and not other_args and not factory_func and not force_field:
                return cst.AnnAssign(target=target, annotation=annotation, value=simple_default)
            if factory_func and factory_value and not other_args and not force_field:
                return cst.AnnAssign(target=target, annotation=annotation, value=cst.Call(func=cst.Name("Factory"), args=[cst.Arg(value=factory_value)]))
            if factory_func and factory_value or other_args or force_field:
                field_args = []
                if factory_func and factory_value:
                    field_args.append(cst.Arg(keyword=cst.Name("factory"), value=factory_value))
                if default_arg and not factory_func:
                    field_args.append(cst.Arg(keyword=cst.Name("default"), value=default_arg))
                for arg in other_args:
                    if arg.keyword:
                        field_args.append(cst.Arg(keyword=arg.keyword, value=arg.value))
                    else:
                        field_args.append(arg)
                return cst.AnnAssign(target=target, annotation=annotation, value=cst.Call(func=cst.Name("field"), args=field_args))
            return cst.AnnAssign(target=target, annotation=annotation, value=None)
        # Assign (no annotation)
        if simple_default and not other_args and not factory_func and not force_field:
            return cst.Assign(targets=[cst.AssignTarget(target=target)], value=simple_default)
        if factory_func and factory_value and not other_args and not force_field:
            return cst.Assign(targets=[cst.AssignTarget(target=target)], value=cst.Call(func=cst.Name("Factory"), args=[cst.Arg(value=factory_value)]))
        if factory_func and factory_value or other_args or force_field:
            field_args = []
            if factory_func and factory_value:
                field_args.append(cst.Arg(keyword=cst.Name("factory"), value=factory_value))
            if default_arg and not factory_func:
                field_args.append(cst.Arg(keyword=cst.Name("default"), value=default_arg))
            for arg in other_args:
                if arg.keyword:
                    field_args.append(cst.Arg(keyword=arg.keyword, value=arg.value))
                else:
                    field_args.append(arg)
            return cst.Assign(targets=[cst.AssignTarget(target=target)], value=cst.Call(func=cst.Name("field"), args=field_args))
        return cst.Assign(targets=[cst.AssignTarget(target=target)], value=target)

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
        args = getattr(original_node.value, "args", [])
        factory_func, factory_value, simple_default, default_arg, other_args = self._parse_field_args(args)
        field_name = original_node.target.value if isinstance(original_node.target, cst.Name) else None
        force_field = field_name in self._decorated_fields
        return self._build_field_value(
            target=original_node.target,
            annotation=original_node.annotation,
            factory_func=factory_func,
            factory_value=factory_value,
            simple_default=simple_default,
            default_arg=default_arg,
            other_args=other_args,
            force_field=force_field,
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
        code_str = updated_node.code if hasattr(updated_node, "code") else str(updated_node)
        # Remove all forms of old imports first
        RemoveImportsVisitor.remove_unused_import(self.context, "attr")
        RemoveImportsVisitor.remove_unused_import(self.context, "attrs")
        RemoveImportsVisitor.remove_unused_import(self.context, "attr", "attrs")
        RemoveImportsVisitor.remove_unused_import(self.context, "attr", "attrib")
        RemoveImportsVisitor.remove_unused_import(self.context, "attr", "ib")
        RemoveImportsVisitor.remove_unused_import(self.context, "attr", "Factory")
        RemoveImportsVisitor.remove_unused_import(self.context, "attrs", "define")
        RemoveImportsVisitor.remove_unused_import(self.context, "attrs", "Factory")
        RemoveImportsVisitor.remove_unused_import(self.context, "attrs", "field")
        # Add imports in the expected order: Factory, define, field
        if "Factory(" in code_str:
            # Check if Factory is already imported from attr using GatherImportsVisitor
            import_visitor = GatherImportsVisitor(self.context)
            updated_node.visit(import_visitor)
            factory_imported_from_attr = (
                "attr" in import_visitor.object_mapping and 
                "Factory" in import_visitor.object_mapping["attr"]
            )
            if not factory_imported_from_attr:
                AddImportsVisitor.add_needed_import(self.context, "attrs", "Factory")
        AddImportsVisitor.add_needed_import(self.context, "attrs", "define")
        if "field(" in code_str:
            AddImportsVisitor.add_needed_import(self.context, "attrs", "field")
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
        factory_func, factory_value, simple_default, default_arg, other_args = self._parse_field_args(remaining_args)
        if type_arg:
            return self._build_field_value(
                target=target,
                annotation=cst.Annotation(annotation=type_arg),
                factory_func=factory_func,
                factory_value=factory_value,
                simple_default=simple_default,
                default_arg=default_arg,
                other_args=other_args,
                force_field=force_field,
            )
        else:
            return self._build_field_value(
                target=target,
                annotation=None,
                factory_func=factory_func,
                factory_value=factory_value,
                simple_default=simple_default,
                default_arg=default_arg,
                other_args=other_args,
                force_field=force_field,
            )

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
