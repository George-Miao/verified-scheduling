#!/usr/bin/env python3
"""
Post-processor to replace calloc with VLAs in generated C code.

This is an UNVERIFIED transformation applied after the verified compilation
pipeline. It transforms heap-allocated intermediate arrays to stack-based VLAs.

Usage: python3 replace_calloc.py <input.c> [output.c]
       If output is omitted, modifies file in-place.
"""

import re
import sys
import argparse
from pathlib import Path


def simplify_expression(expr: str) -> str:
    """
    Simplify arithmetic expressions in VLA size declarations.
    
    Simplifications:
    - (X - (0)) → X
    - (X + (0)) → X
    - (X) * (Y) → X * Y (remove redundant parens)
    - (0) → 0
    """
    # Remove subtracting zero: (X - (0))
    expr = re.sub(r'\(([^)]+)\s*-\s*\(0\)\)', r'\1', expr)
    
    # Remove adding zero: (X + (0))
    expr = re.sub(r'\(([^)]+)\s*\+\s*\(0\)\)', r'\1', expr)
    
    # Remove standalone (0)
    expr = re.sub(r'\(0\)', '0', expr)
    
    # Simplify (X) * (Y) to X * Y - but be careful with precedence
    # Only do this for simple identifiers
    expr = re.sub(r'\((\w+)\)\s*\*\s*\((\w+)\)', r'\1 * \2', expr)
    
    return expr.strip()


def transform_calloc_to_vla(c_code: str) -> tuple[str, dict]:
    """
    Transform calloc/free pairs to VLA declarations.

    Returns:
        (transformed_code, stats_dict)
    """
    stats = {"callocs_replaced": 0, "frees_removed": 0, "warnings": [], "simplifications": 0}

    # Pattern: float *varname = calloc(size_expr, sizeof(float));
    calloc_pattern = r"float \*(\w+) = calloc\(([^,]+), sizeof\(float\)\);"

    def replace_calloc(match):
        var_name = match.group(1)
        size_expr = match.group(2)
        stats["callocs_replaced"] += 1

        # Simplify the size expression
        simplified = simplify_expression(size_expr)
        if simplified != size_expr:
            stats["simplifications"] += 1

        # Check for complex size expressions after simplification
        if "(" in simplified and simplified.count("(") > 1:
            stats["warnings"].append(
                f"Complex size expression for {var_name}: {simplified}"
            )

        # Generate VLA declaration
        return f"float {var_name}[{simplified}];"

    # Replace calloc with VLA
    transformed = re.sub(calloc_pattern, replace_calloc, c_code)

    # Find and comment out corresponding free() calls
    free_pattern = r"free\((\w+)\);"

    def replace_free(match):
        var_name = match.group(1)
        stats["frees_removed"] += 1
        return f"// {var_name} auto-freed (VLA)"

    transformed = re.sub(free_pattern, replace_free, transformed)
    
    # Also simplify existing VLA declarations
    vla_pattern = r'float (\w+)\[([^\]]+)\];'
    
    def simplify_vla(match):
        var_name = match.group(1)
        size_expr = match.group(2)
        simplified = simplify_expression(size_expr)
        
        if simplified != size_expr:
            stats["simplifications"] += 1
        
        return f'float {var_name}[{simplified}];'
    
    transformed = re.sub(vla_pattern, simplify_vla, transformed)
    
    # Simplify expressions in array indexing and other arithmetic
    # Pattern: any expression containing (X - (0)) or similar
    def simplify_all_expressions(code):
        # Keep simplifying until no more changes
        prev = None
        iterations = 0
        while prev != code and iterations < 5:
            prev = code
            # Simplify (X - (0)) anywhere in the code
            code = re.sub(r'\(([^)]+)\s*-\s*\(0\)\)', r'\1', code)
            # Simplify (X + (0)) anywhere
            code = re.sub(r'\(([^)]+)\s*\+\s*\(0\)\)', r'\1', code)
            # Simplify X - 0 (without parentheses around 0)
            code = re.sub(r'(\w+)\s*-\s*0(?!\w)', r'\1', code)
            # Simplify X + 0 (without parentheses around 0)
            code = re.sub(r'(\w+)\s*\+\s*0(?!\w)', r'\1', code)
            # Simplify standalone (0)
            code = re.sub(r'\(0\)', '0', code)
            # Simplify (N) to N for single-digit or simple identifiers
            code = re.sub(r'\((\w+)\)(?=\s*[+\-*/\)])', r'\1', code)
            iterations += 1
        return code
    
    transformed = simplify_all_expressions(transformed)

    return transformed, stats


def process_file(input_path: Path, output_path: Path = None, in_place: bool = False):
    """Process a single C file."""

    if output_path is None and not in_place:
        output_path = input_path.with_suffix(".vla.c")
    elif in_place:
        output_path = input_path

    print(f"Processing: {input_path}")

    # Read input
    with open(input_path, "r") as f:
        original = f.read()

    # Transform
    transformed, stats = transform_calloc_to_vla(original)

    # Write output
    with open(output_path, "w") as f:
        f.write(transformed)

    # Report
    print(f"  ✓ Replaced {stats['callocs_replaced']} calloc() calls")
    print(f"  ✓ Removed {stats['frees_removed']} free() calls")
    print(f"  ✓ Simplified {stats['simplifications']} array size expressions")

    if stats["warnings"]:
        print("  ⚠ Warnings:")
        for warn in stats["warnings"]:
            print(f"    - {warn}")

    if output_path != input_path:
        print(f"  → Output: {output_path}")
    else:
        print(f"  → Modified in-place")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Replace calloc/free with VLAs in generated C code"
    )
    parser.add_argument("input", type=Path, help="Input C file or directory")
    parser.add_argument(
        "-o", "--output", type=Path, help="Output file (for single file) or directory"
    )
    parser.add_argument(
        "-i", "--in-place", action="store_true", help="Modify files in-place"
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Process directory recursively"
    )

    args = parser.parse_args()

    total_stats = {"callocs_replaced": 0, "frees_removed": 0, "files": 0}

    # Process single file
    if args.input.is_file():
        stats = process_file(args.input, args.output, args.in_place)
        total_stats["callocs_replaced"] += stats["callocs_replaced"]
        total_stats["frees_removed"] += stats["frees_removed"]
        total_stats["files"] = 1

    # Process directory
    elif args.input.is_dir():
        pattern = "**/*.c" if args.recursive else "*.c"
        c_files = list(args.input.glob(pattern))

        if not c_files:
            print(f"No .c files found in {args.input}")
            return 1

        print(f"Found {len(c_files)} C files\n")

        for c_file in c_files:
            # Skip output files from previous runs
            if c_file.suffix == ".c" and ".vla" in c_file.stem:
                continue

            try:
                stats = process_file(c_file, None, args.in_place)
                total_stats["callocs_replaced"] += stats["callocs_replaced"]
                total_stats["frees_removed"] += stats["frees_removed"]
                total_stats["files"] += 1
                print()
            except Exception as e:
                print(f"  ✗ Error: {e}\n")

    else:
        print(f"Error: {args.input} not found")
        return 1

    # Summary
    print("=" * 60)
    print(f"Summary: Processed {total_stats['files']} files")
    print(f"         Replaced {total_stats['callocs_replaced']} calloc() calls")
    print(f"         Removed {total_stats['frees_removed']} free() calls")

    return 0


if __name__ == "__main__":
    sys.exit(main())
