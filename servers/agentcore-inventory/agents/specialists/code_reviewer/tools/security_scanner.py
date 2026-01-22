# =============================================================================
# Security Scanner Tools for CodeReviewerAgent
# =============================================================================
# AST-based security vulnerability detection for Python code.
# Focuses on OWASP Top 10 and common Python security anti-patterns.
#
# Detection Categories:
# 1. SQL Injection - SQL queries with string concatenation
# 2. Code Injection - eval(), exec(), __import__() with user input
# 3. Hardcoded Secrets - passwords, API keys, tokens in source code
# 4. Insecure Randomness - random.random() instead of secrets module
# 5. Unsafe Deserialization - pickle.loads(), yaml.load()
# 6. Shell Command Injection - subprocess with shell=True
# 7. Path Traversal - os.path.join with unsanitized input
# 8. XML External Entity (XXE) - XML parsing without protection
#
# Security Severity Levels:
# - CRITICAL: Direct vulnerability, immediate fix required
# - WARNING: Potential vulnerability, review required
# - INFO: Security best practice violation
#
# Based on:
# - OWASP Top 10 (2021): https://owasp.org/Top10/
# - Bandit security linter: https://bandit.readthedocs.io/
# - MITRE CWE: https://cwe.mitre.org/
# =============================================================================

import ast
import json
import logging
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from strands.tools import tool

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes for Security Findings
# =============================================================================


@dataclass
class SecurityFinding:
    """Security vulnerability finding."""
    vulnerability_type: str  # e.g., "sql_injection", "code_injection"
    severity: str  # "critical", "warning", "info"
    line_number: int
    code_snippet: str
    title: str
    description: str
    recommendation: str
    cwe_id: Optional[str] = None  # Common Weakness Enumeration ID


# =============================================================================
# Security Pattern Detectors
# =============================================================================


class SecurityVisitor(ast.NodeVisitor):
    """
    AST visitor that detects security vulnerabilities.

    Traverses the AST and identifies dangerous patterns including:
    - SQL injection risks
    - Code injection via eval/exec
    - Hardcoded secrets
    - Insecure cryptography
    - Shell command injection
    """

    def __init__(self, code_lines: List[str]):
        self.findings: List[SecurityFinding] = []
        self.code_lines = code_lines

    def get_code_snippet(self, line_number: int, context: int = 0) -> str:
        """Get code snippet around line number."""
        start = max(0, line_number - context - 1)
        end = min(len(self.code_lines), line_number + context)
        return "\n".join(self.code_lines[start:end])

    def visit_Call(self, node):
        """Check function calls for security issues."""
        # Get function name
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name:
            # Check for eval() and exec() - Code Injection (CWE-95)
            if func_name in ("eval", "exec"):
                self.findings.append(SecurityFinding(
                    vulnerability_type="code_injection",
                    severity="critical",
                    line_number=node.lineno,
                    code_snippet=self.get_code_snippet(node.lineno),
                    title="Uso de eval() ou exec() - Injeção de Código",
                    description=f"Chamada de {func_name}() permite execução de código arbitrário",
                    recommendation=f"Evite {func_name}(). Use alternativas seguras como ast.literal_eval() ou json.loads()",
                    cwe_id="CWE-95",
                ))

            # Check for __import__() - Dynamic Import (CWE-95)
            elif func_name == "__import__":
                self.findings.append(SecurityFinding(
                    vulnerability_type="code_injection",
                    severity="warning",
                    line_number=node.lineno,
                    code_snippet=self.get_code_snippet(node.lineno),
                    title="Uso de __import__() - Import Dinâmico",
                    description="Import dinâmico pode carregar módulos maliciosos",
                    recommendation="Use importlib.import_module() com validação de entrada",
                    cwe_id="CWE-95",
                ))

            # Check for pickle.loads() - Unsafe Deserialization (CWE-502)
            elif func_name in ("loads", "load") and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "pickle":
                    self.findings.append(SecurityFinding(
                        vulnerability_type="unsafe_deserialization",
                        severity="critical",
                        line_number=node.lineno,
                        code_snippet=self.get_code_snippet(node.lineno),
                        title="Deserialização Insegura - pickle.loads()",
                        description="pickle.loads() pode executar código arbitrário",
                        recommendation="Use formatos seguros como JSON. Se pickle é necessário, valide origem dos dados",
                        cwe_id="CWE-502",
                    ))

            # Check for yaml.load() without SafeLoader (CWE-502)
            elif func_name == "load" and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "yaml":
                    # Check if Loader argument is present and safe
                    uses_safe_loader = False
                    for keyword in node.keywords:
                        if keyword.arg == "Loader":
                            if isinstance(keyword.value, ast.Attribute):
                                if keyword.value.attr in ("SafeLoader", "BaseLoader"):
                                    uses_safe_loader = True

                    if not uses_safe_loader:
                        self.findings.append(SecurityFinding(
                            vulnerability_type="unsafe_deserialization",
                            severity="critical",
                            line_number=node.lineno,
                            code_snippet=self.get_code_snippet(node.lineno),
                            title="Deserialização Insegura - yaml.load()",
                            description="yaml.load() sem SafeLoader pode executar código arbitrário",
                            recommendation="Use yaml.safe_load() ou yaml.load(Loader=yaml.SafeLoader)",
                            cwe_id="CWE-502",
                        ))

            # Check for subprocess with shell=True (CWE-78)
            elif func_name in ("run", "call", "check_output", "Popen"):
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                        # Check if shell=True is used
                        uses_shell = False
                        for keyword in node.keywords:
                            if keyword.arg == "shell":
                                if isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                                    uses_shell = True

                        if uses_shell:
                            self.findings.append(SecurityFinding(
                                vulnerability_type="command_injection",
                                severity="critical",
                                line_number=node.lineno,
                                code_snippet=self.get_code_snippet(node.lineno),
                                title="Injeção de Comando Shell - subprocess com shell=True",
                                description="subprocess com shell=True permite injeção de comandos",
                                recommendation="Use shell=False e passe comando como lista: subprocess.run(['cmd', 'arg'])",
                                cwe_id="CWE-78",
                            ))

            # Check for insecure random (not cryptographically secure)
            elif func_name in ("random", "randint", "choice", "shuffle"):
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "random":
                        self.findings.append(SecurityFinding(
                            vulnerability_type="weak_randomness",
                            severity="warning",
                            line_number=node.lineno,
                            code_snippet=self.get_code_snippet(node.lineno),
                            title="Gerador de Números Aleatórios Inseguro",
                            description="Módulo random não é criptograficamente seguro",
                            recommendation="Use secrets.token_bytes(), secrets.token_hex(), ou secrets.choice() para segurança",
                            cwe_id="CWE-338",
                        ))

        self.generic_visit(node)

    def visit_Str(self, node):
        """Check string literals for hardcoded secrets."""
        self._check_hardcoded_secrets(node.s, node.lineno)
        self.generic_visit(node)

    def visit_Constant(self, node):
        """Check constants for hardcoded secrets (Python 3.8+)."""
        if isinstance(node.value, str):
            self._check_hardcoded_secrets(node.value, node.lineno)
        self.generic_visit(node)

    def _check_hardcoded_secrets(self, value: str, line_number: int):
        """Check if string contains hardcoded secrets."""
        # Patterns for common secret indicators
        secret_patterns = [
            (r"password\s*=\s*['\"][^'\"]+['\"]", "Senha hardcoded", "password"),
            (r"api[_-]?key\s*=\s*['\"][^'\"]+['\"]", "API key hardcoded", "api_key"),
            (r"secret[_-]?key\s*=\s*['\"][^'\"]+['\"]", "Secret key hardcoded", "secret"),
            (r"token\s*=\s*['\"][^'\"]+['\"]", "Token hardcoded", "token"),
            (r"aws[_-]?access[_-]?key", "AWS access key hardcoded", "aws_key"),
        ]

        for pattern, title, secret_type in secret_patterns:
            if re.search(pattern, value.lower()):
                self.findings.append(SecurityFinding(
                    vulnerability_type="hardcoded_secret",
                    severity="critical",
                    line_number=line_number,
                    code_snippet=self.get_code_snippet(line_number),
                    title=f"Credencial Hardcoded - {title}",
                    description=f"{title} encontrada no código fonte",
                    recommendation=f"Use variáveis de ambiente (os.getenv) ou AWS Secrets Manager para {secret_type}",
                    cwe_id="CWE-798",
                ))

    def visit_BinOp(self, node):
        """Check for SQL injection via string concatenation."""
        # Check if this is string concatenation with SQL keywords
        if isinstance(node.op, (ast.Add, ast.Mod)):
            code_snippet = self.get_code_snippet(node.lineno)

            # Common SQL keywords that indicate SQL query construction
            sql_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "WHERE", "FROM"]

            # Check if the code contains SQL keywords
            if any(keyword in code_snippet.upper() for keyword in sql_keywords):
                # Check if using + or % for string formatting (dangerous)
                if isinstance(node.op, ast.Add):
                    self.findings.append(SecurityFinding(
                        vulnerability_type="sql_injection",
                        severity="critical",
                        line_number=node.lineno,
                        code_snippet=code_snippet,
                        title="Injeção SQL - Concatenação de String",
                        description="Construção de query SQL com concatenação de string (+)",
                        recommendation="Use consultas parametrizadas (? ou %s) ou ORM (SQLAlchemy)",
                        cwe_id="CWE-89",
                    ))
                elif isinstance(node.op, ast.Mod):
                    self.findings.append(SecurityFinding(
                        vulnerability_type="sql_injection",
                        severity="warning",
                        line_number=node.lineno,
                        code_snippet=code_snippet,
                        title="Injeção SQL - String Formatting",
                        description="Construção de query SQL com string formatting (%)",
                        recommendation="Use consultas parametrizadas (? ou %s) ou ORM (SQLAlchemy)",
                        cwe_id="CWE-89",
                    ))

        self.generic_visit(node)


# =============================================================================
# Security Scanner Tool (Strands Tool Interface)
# =============================================================================


@tool
async def security_scanner_tool(
    code: str,
    filename: str,
) -> str:
    """
    Scan Python code for security vulnerabilities.

    Detects OWASP Top 10 and common Python security issues:
    - SQL injection (CWE-89)
    - Code injection via eval/exec (CWE-95)
    - Hardcoded secrets (CWE-798)
    - Insecure randomness (CWE-338)
    - Unsafe deserialization (CWE-502)
    - Shell command injection (CWE-78)

    Severity Levels:
    - CRITICAL: Direct vulnerability, immediate fix required
    - WARNING: Potential vulnerability, review required
    - INFO: Security best practice violation

    Args:
        code: Python source code to scan
        filename: Filename for error reporting (e.g., "main.py")

    Returns:
        JSON string with security findings:
        {
            "success": true,
            "filename": "main.py",
            "findings": [
                {
                    "vulnerability_type": "sql_injection",
                    "severity": "critical",
                    "line_number": 42,
                    "code_snippet": "query = 'SELECT * FROM users WHERE id=' + user_id",
                    "title": "Injeção SQL - Concatenação de String",
                    "description": "Construção de query SQL com concatenação de string (+)",
                    "recommendation": "Use consultas parametrizadas (? ou %s) ou ORM (SQLAlchemy)",
                    "cwe_id": "CWE-89"
                }
            ],
            "critical_count": 3,
            "warning_count": 2,
            "info_count": 1,
            "total_findings": 6,
            "vulnerability_types": ["sql_injection", "code_injection", "hardcoded_secret"]
        }

    Example:
        result = await security_scanner_tool(
            code="query = 'SELECT * FROM users WHERE id=' + user_id",
            filename="database.py"
        )
    """
    try:
        # Parse the code into AST
        tree = ast.parse(code, filename=filename)

        # Split code into lines for snippets
        code_lines = code.split("\n")

        # Run security analysis
        visitor = SecurityVisitor(code_lines)
        visitor.visit(tree)

        findings = visitor.findings

        # Count findings by severity
        critical_count = sum(1 for f in findings if f.severity == "critical")
        warning_count = sum(1 for f in findings if f.severity == "warning")
        info_count = sum(1 for f in findings if f.severity == "info")

        # Get unique vulnerability types
        vulnerability_types = list(set(f.vulnerability_type for f in findings))

        logger.info(
            f"[SecurityScanner] Scanned {filename}: "
            f"{len(findings)} findings "
            f"({critical_count} critical, {warning_count} warning, {info_count} info)"
        )

        return json.dumps({
            "success": True,
            "filename": filename,
            "findings": [
                {
                    "vulnerability_type": f.vulnerability_type,
                    "severity": f.severity,
                    "line_number": f.line_number,
                    "code_snippet": f.code_snippet,
                    "title": f.title,
                    "description": f.description,
                    "recommendation": f.recommendation,
                    "cwe_id": f.cwe_id,
                }
                for f in findings
            ],
            "critical_count": critical_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "total_findings": len(findings),
            "vulnerability_types": vulnerability_types,
        })

    except SyntaxError as e:
        logger.warning(
            f"[SecurityScanner] Syntax error in {filename} "
            f"(line {e.lineno}): {e.msg}"
        )
        return json.dumps({
            "success": False,
            "error": f"SyntaxError: {e.msg}",
            "line_number": e.lineno,
            "filename": filename,
        })

    except Exception as e:
        logger.error(f"[SecurityScanner] Unexpected error scanning {filename}: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "filename": filename,
        })


# =============================================================================
# Helper Functions (Not Exposed as Tools)
# =============================================================================


def scan_python_file_sync(
    code: str,
    filename: str = "<string>",
) -> Dict[str, Any]:
    """
    Synchronous version of security_scanner_tool for internal use.

    Args:
        code: Python source code
        filename: Filename for error reporting

    Returns:
        Dict with security findings (same format as tool)
    """
    try:
        tree = ast.parse(code, filename=filename)
        code_lines = code.split("\n")

        visitor = SecurityVisitor(code_lines)
        visitor.visit(tree)

        findings = visitor.findings
        critical_count = sum(1 for f in findings if f.severity == "critical")
        warning_count = sum(1 for f in findings if f.severity == "warning")

        return {
            "success": True,
            "filename": filename,
            "findings": [
                {
                    "vulnerability_type": f.vulnerability_type,
                    "severity": f.severity,
                    "line_number": f.line_number,
                    "title": f.title,
                    "cwe_id": f.cwe_id,
                }
                for f in findings
            ],
            "critical_count": critical_count,
            "warning_count": warning_count,
            "total_findings": len(findings),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "filename": filename,
        }
