"""Tag and tree node defninition for the "unless" tag."""

import sys
from typing import TextIO

from liquid.token import Token
from liquid.token import TOKEN_EOF
from liquid.token import TOKEN_EXPRESSION
from liquid.token import TOKEN_TAG

from liquid.parse import get_parser
from liquid.parse import expect
from liquid.parse import parse_boolean_expression

from liquid.ast import Node
from liquid.ast import BlockNode

from liquid.tag import Tag
from liquid.context import Context
from liquid.stream import TokenStream
from liquid.lex import tokenize_boolean_expression
from liquid.expression import Expression

TAG_UNLESS = sys.intern("unless")
TAG_ENDUNLESS = sys.intern("endunless")

ENDUNLESSBLOCK = (TAG_ENDUNLESS, TOKEN_EOF)


class UnlessNode(Node):
    """Parse tree node for an "unless" template tag."""

    __slots__ = ("tok", "condition", "consequence")

    statement = False

    def __init__(self, tok: Token, condition: Expression, consequence: BlockNode):
        self.tok = tok
        self.condition = condition
        self.consequence = consequence

    def __str__(self) -> str:
        return f"if !{self.condition} {{ {self.consequence} }}"

    def render_to_output(self, context: Context, buffer: TextIO):
        if not self.condition.evaluate(context):
            self.consequence.render(context, buffer)


class UnlessTag(Tag):

    name = TAG_UNLESS
    end = TAG_ENDUNLESS

    def parse(self, stream: TokenStream) -> UnlessNode:
        parser = get_parser(self.env)

        expect(stream, TOKEN_TAG, value=TAG_UNLESS)
        tok = stream.current
        stream.next_token()

        expect(stream, TOKEN_EXPRESSION)
        expr_iter = tokenize_boolean_expression(stream.current.value)
        expr = parse_boolean_expression(TokenStream(expr_iter))

        stream.next_token()
        consequence = parser.parse_block(stream, ENDUNLESSBLOCK)

        expect(stream, TOKEN_TAG, value=TAG_ENDUNLESS)
        return UnlessNode(tok, condition=expr, consequence=consequence)
