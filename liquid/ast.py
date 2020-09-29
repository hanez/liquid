""""""

from abc import ABC, abstractmethod
from io import StringIO
from typing import List, Optional, TextIO

from liquid.token import Token, TOKEN_TAG_NAME
from liquid.context import Context
from liquid.expression import Expression
from liquid.exceptions import DisabledTagError
from liquid.code import Opcode
from liquid.compiler import Compiler


# TODO: Include version number in parse tree


class Node(ABC):
    __slots__ = ()

    statement = True

    def token(self) -> Optional[Token]:
        """The token that started this node."""
        return getattr(self, "tok", None)

    def raise_for_disabled(self, disabled_tags):
        tok = self.token()
        if tok.type == TOKEN_TAG_NAME and tok.value in disabled_tags:
            raise DisabledTagError(
                f"{tok.value} usage is not allowed in this context", linenum=tok.linenum
            )

    def render(self, context: Context, buffer: TextIO) -> Optional[bool]:
        """Check disabled tags before delegating to `render_to_output`."""
        self.raise_for_disabled(context.disabled_tags)
        return self.render_to_output(context, buffer)

    @abstractmethod
    def render_to_output(self, context: Context, buffer: TextIO) -> Optional[bool]:
        """Render this node to the output buffer."""

    def compile_node(self, compiler: Compiler):
        raise NotImplementedError(self.__class__.__name__)

    def compile(self, compiler: Compiler):
        self.compile_node(compiler)

        # Emit a stack pop for any tag that produces an output.
        if self.statement:
            compiler.emit(Opcode.POP)


class ParseTree(Node):
    """The root node of all syntax trees."""

    __slots__ = ("statements",)

    statement = False

    def __init__(self):
        self.statements = []

    def __str__(self):  # pragma: no cover
        return "".join(str(s) for s in self.statements)

    def __repr__(self):
        return f"ParseTree({self.statements})"

    def render_to_output(self, context: Context, buffer: TextIO):
        for stmt in self.statements:
            stmt.render(context, buffer)

    def compile_node(self, compiler: Compiler):
        for stmt in self.statements:
            stmt.compile(compiler)


class IllegalNode(Node):
    """Parse tree node representing an illegal or unregistered tag.

    Illegal nodes are necesary when running in "warning" or "lax" mode. In
    strict mode, an excpetions should be raised as soon as an illegal token
    is found.
    """

    __slots__ = ("tok",)

    def __init__(self, tok: Token):
        self.tok = tok

    def __str__(self) -> str:
        return ""

    def __repr__(self) -> str:  # pragma: no cover
        return f"IllegalNode(tok={self.tok})"

    def render_to_output(self, context: Context, buffer: TextIO):
        pass


class BlockNode(Node):
    __slots__ = ("tok", "statements")

    def __init__(self, tok: Token, statements: List[Node] = None):
        self.tok = tok
        self.statements = statements or []

    def __str__(self):
        return "".join(str(s) for s in self.statements)

    def render_to_output(self, context: Context, buffer: TextIO):
        # This intermediate buffer is used to suppress blocks that contain only
        # whitespace.
        buf = StringIO()

        for stmt in self.statements:
            try:
                stmt.render(context, buf)
            except:
                # Write what we have so far. We might be in warn or lax mode.
                val = buf.getvalue()
                if not val.isspace():
                    buffer.write(val)

                # FIXME: We probably need to warn and continue when in WARN mode.
                # Or ignore and continue in LAX mode.
                raise

        # Don't write to the ouput buffer if the block contains only whitespace.
        val = buf.getvalue()
        if not val.isspace():
            buffer.write(val)

    def compile(self, compiler: Compiler):
        for stmt in self.statements:
            stmt.compile(compiler)


class ConditionalBlockNode(Node):
    __slots__ = ("tok", "condition", "block")

    def __init__(self, tok: Token, condition: Expression, block: BlockNode = None):
        self.tok = tok
        self.condition = condition
        self.block = block

    def __str__(self):
        return f"{self.condition} {{ {self.block} }}"

    def render_to_output(self, context: Context, buffer: TextIO):
        if self.condition.evaluate(context):
            self.block.render(context, buffer)
            return True
        return False
