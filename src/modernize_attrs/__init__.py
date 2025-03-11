from typing import Union
import libcst as cst
from libcst import matchers as m
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand
from libcst.codemod.visitors import AddImportsVisitor, RemoveImportsVisitor

class ModernizeAttrsCodemod(VisitorBasedCodemodCommand):
    """
    Codemod that converts @attrs.s decorators to @define from attrs package.
    """

    DESCRIPTION = "Converts @attrs.s decorators to @define from attrs"
    ATTR_IB_MATCHER = m.Call(
        func=m.OneOf(
            m.Attribute(value=m.Name(value="attrs"), attr=m.Name(value="ib")),
            m.Attribute(value=m.Name(value="attr"), attr=m.Name(value="ib")),
        )
    )
    ATTR_S_MATCHER = m.Decorator(
        decorator=m.OneOf(
            m.Attribute(value=m.Name(value="attrs"), attr=m.Name(value="s")),
            m.Attribute(value=m.Name(value="attr"), attr=m.Name(value="s")),
        )
    )

    def __init__(self, context: CodemodContext) -> None:
        super().__init__(context)
        self.current_class_has_untyped_attr = False
        self.current_class_name = None

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self.current_class_has_untyped_attr = False
        self.current_class_name = node.name.value

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        if self.current_class_has_untyped_attr:
            print(f"Warning: Skipping class {self.current_class_name} because it contains attr.ib() without type hints")
            return original_node

        self._update_imports()
        return updated_node

    def _update_imports(self) -> None:
        """Update imports when processing a class."""
        AddImportsVisitor.add_needed_import(self.context, "attrs", "define")
        AddImportsVisitor.add_needed_import(self.context, "attrs", "field")
        RemoveImportsVisitor.remove_unused_import(self.context, "attr")
        RemoveImportsVisitor.remove_unused_import(self.context, "attrs")

    def _extract_attr_args(self, node: cst.Call) -> tuple[cst.BaseExpression | None, list[cst.Arg]]:
        """Extract type argument and remaining arguments from attr.ib() call."""
        type_arg = None
        remaining_args = []
        
        if hasattr(node, 'args'):
            for arg in node.args:
                if m.matches(arg, m.Arg(keyword=m.Name(value="type"))):
                    type_arg = arg.value
                else:
                    remaining_args.append(arg)
        
        return type_arg, remaining_args

    @m.call_if_inside(m.ClassDef())
    def visit_Call(self, node: cst.Call) -> None:
        if m.matches(node, self.ATTR_IB_MATCHER):
            has_type = any(
                m.matches(arg, m.Arg(keyword=m.Name(value="type")))
                for arg in node.args
            )
            if not has_type:
                self.current_class_has_untyped_attr = True

    @m.call_if_inside(m.ClassDef())
    def leave_Decorator(
        self, original_node: cst.Decorator, updated_node: cst.Decorator
    ) -> Union[cst.Decorator, cst.RemovalSentinel]:
        if self.current_class_has_untyped_attr:
            return updated_node

        if m.matches(original_node, self.ATTR_S_MATCHER):
            return cst.Decorator(decorator=cst.Name(value="define"))

        return updated_node

    def leave_Module(
        self, original_node: cst.Module, updated_node: cst.Module
    ) -> cst.Module:
        import_define = cst.ImportFrom(
            module=cst.Name(value="attrs"), 
            names=[cst.ImportAlias(name=cst.Name(value="define"))]
        )

        if ("import", "attrs", "define") in self.context.scratch:
            return updated_node.with_changes(body=[import_define, *updated_node.body])

        return updated_node

    @m.call_if_inside(m.ClassDef())
    def leave_AnnAssign(
        self, original_node: cst.AnnAssign, updated_node: cst.AnnAssign
    ) -> cst.AnnAssign:
        if self.current_class_has_untyped_attr or not m.matches(original_node.value, self.ATTR_IB_MATCHER):
            return updated_node

        _, remaining_args = self._extract_attr_args(original_node.value)
        if not remaining_args:
            return cst.AnnAssign(
                target=original_node.target,
                annotation=original_node.annotation,
                value=None
            )

        return updated_node.with_changes(
            value=cst.Call(
                func=cst.Name(value="field"),
                args=remaining_args
            )
        )

    @m.call_if_inside(m.ClassDef())
    def leave_Assign(
        self, original_node: cst.Assign, updated_node: cst.Assign
    ) -> Union[cst.Assign, cst.AnnAssign]:
        if self.current_class_has_untyped_attr or not m.matches(original_node.value, self.ATTR_IB_MATCHER):
            return updated_node

        type_arg, remaining_args = self._extract_attr_args(original_node.value)
        target = original_node.targets[0].target

        if type_arg:
            if not remaining_args:
                return cst.AnnAssign(
                    target=target,
                    annotation=cst.Annotation(annotation=type_arg),
                    value=None
                )
            
            return cst.AnnAssign(
                target=target,
                annotation=cst.Annotation(annotation=type_arg),
                value=cst.Call(
                    func=cst.Name(value="field"),
                    args=remaining_args
                )
            )
        
        if remaining_args:
            return cst.Assign(
                targets=[cst.AssignTarget(target=target)],
                value=cst.Call(
                    func=cst.Name(value="field"),
                    args=remaining_args
                )
            )
        
        return cst.Assign(
            targets=[cst.AssignTarget(target=target)],
            value=target
        )
