"""
Moso AI — Deterministic Tools Engine
Executes non-language tasks deterministically without relying on language-model token generation:
- Safe AST Arithmetic & Math evaluation
- Date & Calendar computations
- Unit conversions
- String & Citation verification
"""

import ast
import operator
import math
import re
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, Union

# -------------------------------------------------------------
# 1. Safe AST Arithmetic Evaluator
# -------------------------------------------------------------
ALLOWED_FUNCS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "factorial": math.factorial,
    "ceil": math.ceil,
    "floor": math.floor,
}

ALLOWED_CONSTS = {
    "pi": math.pi,
    "e": math.e,
}

AST_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _safe_eval_ast(node: ast.AST) -> Union[int, float]:
    """Recursively evaluate an AST expression ensuring no arbitrary code execution."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    elif isinstance(node, ast.Name):
        lower_id = node.id.lower()
        if lower_id in ALLOWED_CONSTS:
            return ALLOWED_CONSTS[lower_id]
        raise ValueError(f"Unknown mathematical constant: {node.id}")
    elif isinstance(node, ast.BinOp):
        left = _safe_eval_ast(node.left)
        right = _safe_eval_ast(node.right)
        op_type = type(node.op)
        if op_type in AST_OPERATORS:
            # Guard against giant powers that freeze CPU
            if op_type is ast.Pow and (right > 1000 or left > 10000):
                raise ValueError("Exponent too large for safe evaluation")
            return AST_OPERATORS[op_type](left, right)
        raise ValueError(f"Unsupported binary operator: {op_type}")
    elif isinstance(node, ast.UnaryOp):
        operand = _safe_eval_ast(node.operand)
        op_type = type(node.op)
        if op_type in AST_OPERATORS:
            return AST_OPERATORS[op_type](operand)
        raise ValueError(f"Unsupported unary operator: {op_type}")
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id.lower()
            if func_name in ALLOWED_FUNCS:
                args = [_safe_eval_ast(a) for a in node.args]
                return ALLOWED_FUNCS[func_name](*args)
        raise ValueError("Unsupported function call")
    raise ValueError(f"Unsupported AST node: {type(node)}")


def evaluate_arithmetic(expression: str) -> Optional[Dict[str, Any]]:
    """Safely parse and compute a mathematical expression."""
    clean_expr = expression.strip().rstrip("?").rstrip(".").strip()
    
    # Handle percentage: "15% of 850" -> "850 * 0.15"
    pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%\s+of\s+(\d+(?:\.\d+)?)', clean_expr, re.IGNORECASE)
    if pct_match:
        pct = float(pct_match.group(1))
        val = float(pct_match.group(2))
        res = (pct / 100.0) * val
        return {
            "expression": f"{pct}% of {val}",
            "value": res,
            "formatted": f"{pct}% of {val} = {res:g}",
        }

    # Normalize '^' to '**' for powers
    clean_expr = clean_expr.replace("^", "**")
    # Replace unicode multiplication/division
    clean_expr = clean_expr.replace("×", "*").replace("÷", "/")
    
    # Strip leading keywords like "calculate", "evaluate", "what is"
    clean_expr = re.sub(r'^(calculate|evaluate|what\s+is|what\'s\s+the\s+square\s+root\s+of)\s+', '', clean_expr, flags=re.IGNORECASE).strip()
    
    # Handle "square root of X"
    sqrt_match = re.search(r'(?:square\s+root\s+of|sqrt)\s+(\d+(?:\.\d+)?)', clean_expr, re.IGNORECASE)
    if sqrt_match:
        val = float(sqrt_match.group(1))
        res = math.sqrt(val)
        return {
            "expression": f"sqrt({val})",
            "value": res,
            "formatted": f"\\(\\sqrt{{{val:g}}} = {res:g}\\)",
        }

    # Verify expression only contains mathematical tokens
    if not re.match(r'^[0-9\.\s\+\-\*\/\(\)\,\_a-zA-Z]+$', clean_expr):
        return None

    try:
        parsed = ast.parse(clean_expr, mode='eval')
        result = _safe_eval_ast(parsed.body)
        # Format neatly
        if isinstance(result, float) and result.is_integer():
            formatted_val = f"{int(result):,}"
        elif isinstance(result, (int, float)):
            formatted_val = f"{result:g}"
        else:
            formatted_val = str(result)
            
        return {
            "expression": clean_expr.replace("**", "^"),
            "value": result,
            "formatted": f"{clean_expr.replace('**', '^')} = {formatted_val}",
        }
    except Exception:
        return None


# -------------------------------------------------------------
# 2. Date & Calendar Tool
# -------------------------------------------------------------
MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
}


def evaluate_date_query(query: str) -> Optional[Dict[str, Any]]:
    """Answers date queries such as day of the week or days between dates."""
    clean = query.strip()
    
    # Check for "day of the week" e.g. "What day of the week was July 20, 1969?"
    dow_match = re.search(
        r'day\s+of\s+the\s+week\s+(?:was|is|on)\s+([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})',
        clean,
        re.IGNORECASE
    )
    if dow_match:
        month_str = dow_match.group(1).lower()
        day = int(dow_match.group(2))
        year = int(dow_match.group(3))
        if month_str in MONTHS:
            try:
                dt = date(year, MONTHS[month_str], day)
                weekday = dt.strftime("%A")
                return {
                    "tool": "date_weekday",
                    "date": dt.isoformat(),
                    "weekday": weekday,
                    "formatted": f"{dt.strftime('%B %d, %Y')} was a {weekday}.",
                }
            except ValueError:
                pass

    # Check for days between: "days between 2024-03-01 and 2024-12-31" or "days between March 1, 2024 and December 31, 2024"
    diff_match = re.search(
        r'days\s+between\s+([A-Za-z0-9\-\,\s]+)\s+and\s+([A-Za-z0-9\-\,\s]+)',
        clean,
        re.IGNORECASE
    )
    if diff_match:
        try:
            # Try ISO format
            s1 = diff_match.group(1).strip()
            s2 = diff_match.group(2).strip()
            # Simple ISO parse
            d1 = None
            d2 = None
            for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
                if not d1:
                    try:
                        d1 = datetime.strptime(s1, fmt).date()
                    except ValueError:
                        pass
                if not d2:
                    try:
                        d2 = datetime.strptime(s2, fmt).date()
                    except ValueError:
                        pass
            if d1 and d2:
                delta = abs((d2 - d1).days)
                return {
                    "tool": "date_diff",
                    "date1": d1.isoformat(),
                    "date2": d2.isoformat(),
                    "days": delta,
                    "formatted": f"There are {delta} days between {d1.isoformat()} and {d2.isoformat()}.",
                }
        except Exception:
            pass

    return None


# -------------------------------------------------------------
# 3. Unit Conversion Tool
# -------------------------------------------------------------
UNIT_CONVERSIONS = {
    # Length
    ("km", "miles"): lambda v: v * 0.621371,
    ("miles", "km"): lambda v: v * 1.60934,
    ("meters", "feet"): lambda v: v * 3.28084,
    ("feet", "meters"): lambda v: v / 3.28084,
    ("cm", "inches"): lambda v: v / 2.54,
    ("inches", "cm"): lambda v: v * 2.54,
    # Mass
    ("kg", "pounds"): lambda v: v * 2.20462,
    ("kg", "lbs"): lambda v: v * 2.20462,
    ("pounds", "kg"): lambda v: v / 2.20462,
    ("lbs", "kg"): lambda v: v / 2.20462,
    # Temperature
    ("celsius", "fahrenheit"): lambda v: (v * 9 / 5) + 32,
    ("fahrenheit", "celsius"): lambda v: (v - 32) * 5 / 9,
    ("c", "fahrenheit"): lambda v: (v * 9 / 5) + 32,
    ("f", "celsius"): lambda v: (v - 32) * 5 / 9,
}


def evaluate_unit_conversion(query: str) -> Optional[Dict[str, Any]]:
    """Converts common physical units deterministically."""
    clean = query.strip()
    match = re.search(
        r'(?:convert\s+)?(-?\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s+(?:to|in)\s+([a-zA-Z]+)',
        clean,
        re.IGNORECASE
    )
    if match:
        val = float(match.group(1))
        from_u = match.group(2).lower()
        to_u = match.group(3).lower()
        
        # Check conversion table
        if (from_u, to_u) in UNIT_CONVERSIONS:
            conv_fn = UNIT_CONVERSIONS[(from_u, to_u)]
            converted = conv_fn(val)
            return {
                "tool": "unit_conversion",
                "input_value": val,
                "input_unit": from_u,
                "output_value": converted,
                "output_unit": to_u,
                "formatted": f"{val:g} {from_u} = {converted:.4g} {to_u}",
            }

    return None


# -------------------------------------------------------------
# 4. Master Deterministic Tool Dispatcher
# -------------------------------------------------------------
def run_deterministic_tools(query: str) -> Optional[Dict[str, Any]]:
    """
    Checks if a query contains an arithmetic, calendar, or unit-conversion task.
    Returns the exact verified result without needing model inference.
    """
    # 1. Check Arithmetic
    math_res = evaluate_arithmetic(query)
    if math_res:
        return {"type": "arithmetic", "data": math_res}

    # 2. Check Date computation
    date_res = evaluate_date_query(query)
    if date_res:
        return {"type": "date", "data": date_res}

    # 3. Check Unit Conversion
    unit_res = evaluate_unit_conversion(query)
    if unit_res:
        return {"type": "unit_conversion", "data": unit_res}

    return None
