#!/usr/bin/env python3
"""
Generate CLI wrapper for ATL library functions.

Usage:
    ./wrap.py [function_name] arg1 arg2 ... @array1.json @array2.json [--output-size N]

Example:
    ./wrap.py blurtwo 10 20 @input.json --output-size 200
    ./wrap.py im2col 5 10 15 20 25 @x.json @w.json --output-size 150
"""

import re
import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional


class FunctionSignature:
    """Represents a parsed C function signature."""
    
    def __init__(self, name: str, return_type: str, params: List[Tuple[str, str]]):
        self.name = name
        self.return_type = return_type
        self.params = params  # [(type, name), ...]
    
    def __repr__(self):
        params_str = ", ".join(f"{t} {n}" for t, n in self.params)
        return f"{self.return_type} {self.name}({params_str})"


class HeaderParser:
    """Parse C header files to extract function signatures."""
    
    @staticmethod
    def parse_header_file(header_path: Path) -> Optional[FunctionSignature]:
        """Extract function signature from a .h file."""
        with open(header_path, 'r') as f:
            content = f.read()
        
        # Pattern: return_type function_name(params);
        # Match void/int/float func(...)
        pattern = r'(void|int|float)\s+(\w+)\s*\((.*?)\)\s*;'
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        
        if not match:
            return None
        
        return_type = match.group(1)
        func_name = match.group(2)
        params_str = match.group(3)
        
        # Parse parameters
        params = HeaderParser._parse_parameters(params_str)
        
        return FunctionSignature(func_name, return_type, params)
    
    @staticmethod
    def _parse_parameters(params_str: str) -> List[Tuple[str, str]]:
        """Parse parameter list string into (type, name) tuples."""
        params = []
        
        # Split by comma, but be careful with nested types
        param_list = [p.strip() for p in params_str.split(',')]
        
        for param in param_list:
            if not param:
                continue
            
            # Pattern: type name or type* name
            # Handle: float* x, int N, float*output
            parts = param.rsplit(None, 1)
            if len(parts) == 2:
                param_type, param_name = parts
                params.append((param_type, param_name))
            elif len(parts) == 1:
                # Might be "float*x" without space
                m = re.match(r'(\w+\*?)(\w+)', parts[0])
                if m:
                    params.append((m.group(1), m.group(2)))
        
        return params
    
    @staticmethod
    def scan_lib_directory(lib_dir: Path) -> Dict[str, FunctionSignature]:
        """Scan all .h files in directory and build function registry."""
        registry = {}
        
        for header_file in lib_dir.glob('*.h'):
            sig = HeaderParser.parse_header_file(header_file)
            if sig:
                registry[sig.name] = sig
        
        return registry


class ArrayLoader:
    """Load and validate JSON array files."""
    
    @staticmethod
    def load_json_array(filepath: str) -> List[float]:
        """Load JSON file and flatten to 1D array."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Flatten nested arrays
        flat = ArrayLoader._flatten(data)
        
        # Validate all numeric
        if not all(isinstance(x, (int, float)) for x in flat):
            raise ValueError(f"Non-numeric values in {filepath}")
        
        return [float(x) for x in flat]
    
    @staticmethod
    def _flatten(data):
        """Recursively flatten nested lists."""
        if isinstance(data, list):
            result = []
            for item in data:
                result.extend(ArrayLoader._flatten(item))
            return result
        else:
            return [data]


class ConstantFolder:
    """Perform constant folding on C code."""
    
    def __init__(self, param_values: Dict[str, int]):
        self.param_values = param_values
    
    def fold_expression(self, expr: str) -> str:
        """Evaluate expression to constant if possible."""
        # Replace parameter names with their values
        result = expr
        for param, value in self.param_values.items():
            result = re.sub(r'\b' + param + r'\b', str(value), result)
        
        # Try to evaluate the expression
        try:
            # Remove whitespace
            result = result.strip()
            # Safe evaluation of arithmetic expressions
            evaluated = eval(result, {"__builtins__": {}}, {})
            return str(evaluated)
        except:
            # If evaluation fails, return simplified expression
            return result
    
    def fold_code(self, code: str) -> str:
        """Fold all constant expressions in code."""
        # Replace parameter names with constants
        result = code
        for param, value in self.param_values.items():
            result = re.sub(r'\b' + param + r'\b', str(value), result)
        
        # Fold array size expressions [expr]
        def fold_array_size(match):
            expr = match.group(1)
            try:
                folded = eval(expr, {"__builtins__": {}}, {})
                return f'[{folded}]'
            except:
                return match.group(0)
        
        result = re.sub(r'\[([^\]]+)\]', fold_array_size, result)
        
        # Fold arithmetic expressions in loop bounds and conditionals
        # Pattern: number op number -> result
        def fold_arithmetic(match):
            expr = match.group(1)
            try:
                folded = eval(expr, {"__builtins__": {}}, {})
                return str(folded)
            except:
                return match.group(0)
        
# Fold expressions in specific contexts to avoid breaking variable names
        # Only fold in: loop bounds (< expr, <= expr), array sizes [expr]
        # Pattern for loop bounds: < digit op digit
        def fold_in_comparison(match):
            prefix = match.group(1)
            expr = match.group(2)
            try:
                folded = eval(expr, {"__builtins__": {}}, {})
                return f'{prefix}{folded}'
            except:
                return match.group(0)
        
        result = re.sub(r'(<\s*|<=\s*|>\s*|>=\s*)((?:\d+|\()\s*[+\-*/]\s*(?:\d+|\)))', fold_in_comparison, result)
        
        # Multiple passes for nested expressions in comparisons
        for _ in range(3):
            prev = result
            result = re.sub(r'(<\s*|<=\s*|>\s*|>=\s*)((?:\d+|\()\s*[+\-*/]\s*(?:\d+|\)))', fold_in_comparison, result)
            if result == prev:
                break
        
        return result


class WrapperGenerator:
    """Generate C wrapper code."""
    
    def __init__(self, func_sig: FunctionSignature, lib_dir: Path):
        self.func_sig = func_sig
        self.lib_dir = lib_dir
    
    def read_function_body(self) -> Optional[str]:
        """Read the function implementation from .c file."""
        c_file = self.lib_dir / f"{self.func_sig.name}.c"
        if not c_file.exists():
            return None
        
        with open(c_file, 'r') as f:
            content = f.read()
        
        # Extract function body (everything between { and })
        pattern = rf'void\s+{self.func_sig.name}\s*\([^)]+\)\s*\{{'
        match = re.search(pattern, content)
        if not match:
            return None
        
        # Find matching closing brace
        start = match.end()
        brace_count = 1
        pos = start
        
        while pos < len(content) and brace_count > 0:
            if content[pos] == '{':
                brace_count += 1
            elif content[pos] == '}':
                brace_count -= 1
            pos += 1
        
        return content[start:pos-1].strip()
    
    def generate(self, int_args: List[int], array_args: List[List[float]], 
                 output_size: int, inline: bool = True) -> str:
        """Generate complete C wrapper program."""
        
        code = []
        
        # Includes
        if not inline:
            code.append(f'#include "{self.func_sig.name}.h"')
        else:
            code.append('#include <stdlib.h>')
        code.append('#include <stdio.h>')
        code.append('')
        
        # Main function
        code.append('int main() {')
        
        # Generate static array declarations
        array_idx = 0
        for i, (param_type, param_name) in enumerate(self.func_sig.params):
            if param_type.endswith('*') and 'output' not in param_name.lower():
                # Input array
                if array_idx < len(array_args):
                    arr_data = array_args[array_idx]
                    arr_size = len(arr_data)
                    
                    # Declaration with initializer
                    code.append(f'    float {param_name}[{arr_size}] = {{')
                    
                    # Format data (10 values per line)
                    for j in range(0, len(arr_data), 10):
                        chunk = arr_data[j:j+10]
                        values = ', '.join(f'{v:.6f}' for v in chunk)
                        code.append(f'        {values}' + (',' if j + 10 < len(arr_data) else ''))
                    
                    code.append('    };')
                    array_idx += 1

        # Output array
        code.append(f'    float output[{output_size}] = {{0}};')
        code.append('')
        
        # Function call
        call_args = []
        array_idx = 0
        int_idx = 0
        
        for param_type, param_name in self.func_sig.params:
            if param_type.endswith('*'):
                if 'output' in param_name.lower():
                    call_args.append('output')
                else:
                    call_args.append(param_name)
                    array_idx += 1
            else:
                # int parameter
                if int_idx < len(int_args):
                    call_args.append(str(int_args[int_idx]))
                    int_idx += 1
        
        if inline:
            # Inline the function body with constant folding
            func_body = self.read_function_body()
            if func_body:
                # Build parameter value mapping
                param_values = {}
                array_idx = 0
                int_idx = 0
                
                for param_type, param_name in self.func_sig.params:
                    if param_type.endswith('*'):
                        # Skip pointer parameters (arrays)
                        if 'output' not in param_name.lower():
                            array_idx += 1
                    else:
                        # Map int parameter to its value
                        if int_idx < len(int_args):
                            param_values[param_name] = int_args[int_idx]
                            int_idx += 1
                
                # Perform constant folding
                folder = ConstantFolder(param_values)
                folded_body = folder.fold_code(func_body)
                
                # Initialize VLAs to zero in the folded body
                # Pattern: float varname[size]; -> float varname[size] = {0};
                folded_body = re.sub(r'(float \w+\[[^\]]+\]);', r'\1 = {0};', folded_body)
                
                code.append('    // Inlined and constant-folded function body')
                # Indent the function body
                for line in folded_body.split('\n'):
                    if line.strip():
                        code.append('    ' + line)
                code.append('')
            else:
                # Fall back to function call if can't inline
                call_str = ', '.join(call_args)
                code.append(f'    {self.func_sig.name}({call_str});')
                code.append('')
        else:
            # Original function call
            call_str = ', '.join(call_args)
            code.append(f'    {self.func_sig.name}({call_str});')
            code.append('')
        
        # Print output
        code.append('    // Print output')
        code.append(f'    for (int i = 0; i < {output_size}; i++) {{')
        code.append('        printf("%f ", output[i]);')
        code.append('        if ((i + 1) % 10 == 0) printf("\\n");')
        code.append('    }')
        code.append('    printf("\\n");')
        code.append('')
        code.append('    return 0;')
        code.append('}')
        
        return '\n'.join(code)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Generate CLI wrapper for ATL library functions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ./wrap.py blurtwo 10 20 @input.json --output-size 200
  ./wrap.py im2col 5 10 15 20 25 @x.json @w.json --output-size 150 --compile
        """
    )
    
    parser.add_argument('function_name', help='Name of the library function')
    parser.add_argument('args', nargs='+', help='Arguments: numbers or @array.json')
    parser.add_argument('--output-size', type=int, required=True,
                       help='Size of output array')
    parser.add_argument('--lib-dir', type=Path,
                       default=Path(__file__).parent,
                       help='Directory containing library headers')
    parser.add_argument('--output', '-o', type=Path,
                       help='Output C file (default: wrapper_FUNC.c)')
    parser.add_argument('--compile', action='store_true',
                       help='Compile the generated wrapper')
    parser.add_argument('--run', action='store_true',
                       help='Compile and run the wrapper')
    parser.add_argument('--inline', action='store_true', default=True,
                       help='Inline function body with constant folding (default: True)')
    parser.add_argument('--no-inline', action='store_true',
                       help='Disable inlining, use function call instead')
    
    return parser.parse_args()


def main():
    args = parse_args()
    
    # Scan library directory
    print(f"Scanning library directory: {args.lib_dir}")
    registry = HeaderParser.scan_lib_directory(args.lib_dir)
    
    if not registry:
        print("Error: No functions found in library directory")
        return 1
    
    print(f"Found {len(registry)} functions: {', '.join(registry.keys())}")

    # Find target function
    if args.function_name not in registry:
        print(f"Error: Function '{args.function_name}' not found")
        print(f"Available functions: {', '.join(sorted(registry.keys()))}")
        return 1
    
    func_sig = registry[args.function_name]
    print(f"Function signature: {func_sig}")
    
    # Parse arguments
    int_args = []
    array_args = []
    
    for arg in args.args:
        if arg.startswith('@'):
            # Array argument
            filepath = arg[1:]
            print(f"Loading array from: {filepath}")
            try:
                arr_data = ArrayLoader.load_json_array(filepath)
                array_args.append(arr_data)
                print(f"  Loaded {len(arr_data)} elements")
            except Exception as e:
                print(f"Error loading {filepath}: {e}")
                return 1
        else:
            # Numeric argument
            try:
                int_args.append(int(arg))
            except ValueError:
                print(f"Error: Invalid numeric argument '{arg}'")
                return 1
    
    # Type checking
    expected_int_count = sum(1 for t, n in func_sig.params 
                            if not t.endswith('*'))
    expected_array_count = sum(1 for t, n in func_sig.params 
                              if t.endswith('*') and 'output' not in n.lower())
    
    if len(int_args) != expected_int_count:
        print(f"Error: Expected {expected_int_count} int arguments, got {len(int_args)}")
        return 1
    
    if len(array_args) != expected_array_count:
        print(f"Error: Expected {expected_array_count} array arguments, got {len(array_args)}")
        return 1
    
    # Generate wrapper
    print("\nGenerating wrapper code...")
    inline = not args.no_inline
    generator = WrapperGenerator(func_sig, args.lib_dir)
    code = generator.generate(int_args, array_args, args.output_size, inline=inline)
    
    # Write output
    output_file = args.output or Path(f'wrapper_{args.function_name}.c')
    with open(output_file, 'w') as f:
        f.write(code)
    
    print(f"Generated: {output_file}")
    
    # Compile if requested
    if args.compile or args.run:
        import subprocess
        compile_cmd = [
            'clang', '-I.', str(output_file), 'libscheds.a',
            '-o', output_file.stem, '-lm'
        ]
        print(f"\nCompiling: {' '.join(compile_cmd)}")
        result = subprocess.run(compile_cmd, cwd=args.lib_dir)
        
        if result.returncode != 0:
            print("Compilation failed")
            return 1
        
        print(f"Compiled: {output_file.stem}")
        
        # Run if requested
        if args.run:
            print(f"\nRunning {output_file.stem}...")
            print("=" * 60)
            result = subprocess.run([f'./{output_file.stem}'], cwd=args.lib_dir)
            print("=" * 60)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
