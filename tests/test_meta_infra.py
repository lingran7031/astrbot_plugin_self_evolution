import pytest


def test_validate_ast_security_dangerous_import(meta_infra):
    """测试 AST 安全校验 - 危险导入"""
    dangerous_code = "import subprocess\nsubprocess.run('ls')"
    result = meta_infra._validate_ast_security(dangerous_code)
    assert result is not None
    assert "危险导入" in result or "禁止" in result


def test_validate_ast_security_dangerous_func(meta_infra):
    """测试 AST 安全校验 - 危险函数"""
    dangerous_code = "eval('1+1')"
    result = meta_infra._validate_ast_security(dangerous_code)
    assert result is not None
    assert "禁止" in result or "高危" in result


def test_validate_ast_security_valid_code(meta_infra):
    """测试 AST 安全校验 - 有效代码"""
    valid_code = "def hello():\n    print('hello world')"
    result = meta_infra._validate_ast_security(valid_code)
    assert result is None


def test_validate_ast_syntax_error(meta_infra):
    """测试 AST 校验 - 语法错误"""
    invalid_code = "def hello(:\n    print('missing paren')"
    result = meta_infra._validate_ast_security(invalid_code)
    assert result is not None
    assert "语法" in result or "错误" in result
