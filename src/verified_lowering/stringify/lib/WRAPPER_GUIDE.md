# ATL Library Wrapper Generator

## Overview

`wrap.py` is a CLI tool that generates C wrapper programs for testing ATL library functions. It eliminates boilerplate by automatically:

- Parsing function signatures from header files
- Type-checking arguments
- Loading arrays from JSON files
- Generating standalone C programs with static array initialization
- Compiling and running test programs

## Quick Start

```bash
# List available functions
./wrap.py nonexistent 0 --output-size 1

# Generate wrapper for blurtwo
./wrap.py blurtwo 4 5 @test_input.json --output-size 20

# Generate, compile, and run
./wrap.py blurtwo 4 5 @test_input.json --output-size 20 --run

# Complex function with multiple arrays
./wrap.py im2col 2 3 2 1 1 @test_x.json @test_w.json --output-size 12 --run
```

## Usage

```
./wrap.py [function_name] arg1 arg2 ... @array1.json @array2.json --output-size N [options]
```

### Arguments

- **function_name**: Name of the library function (e.g., `blurtwo`, `im2col`)
- **Numeric arguments**: Integer parameters (e.g., dimensions, sizes)
- **Array arguments**: JSON files prefixed with `@` (e.g., `@input.json`)
- **--output-size N**: Size of output array (required)

### Options

- `--compile`: Compile the generated wrapper
- `--run`: Compile and run the wrapper
- `--output FILE`: Specify output C file (default: `wrapper_FUNC.c`)
- `--lib-dir DIR`: Specify library directory (default: current directory)

## JSON Array Format

Arrays can be flat or nested. Nested arrays are automatically flattened:

**Flat array:**

```json
[1.0, 2.0, 3.0, 4.0, 5.0]
```

**Nested array (2D matrix):**

```json
[
    [1.0, 2.0, 3.0],
    [4.0, 5.0, 6.0],
    [7.0, 8.0, 9.0]
]
```

Both are converted to 1D C arrays with proper initialization.

## Examples

### Example 1: Simple Blur Function

**Function signature:**

```c
void blurtwo(float* v, int M, int N, float* output);
```

**Input data** (`test_input.json`):

```json
[
    [1.0, 2.0, 3.0, 4.0, 5.0],
    [6.0, 7.0, 8.0, 9.0, 10.0],
    [11.0, 12.0, 13.0, 14.0, 15.0],
    [16.0, 17.0, 18.0, 19.0, 20.0]
]
```

**Command:**

```bash
./wrap.py blurtwo 4 5 @test_input.json --output-size 20 --run
```

**Generated wrapper** (`wrapper_blurtwo.c`):

```c
#include "blurtwo.h"
#include <stdio.h>

int main() {
    float v[20] = {
        1.000000, 2.000000, 3.000000, 4.000000, 5.000000, 6.000000, 7.000000, 8.000000, 9.000000, 10.000000,
        11.000000, 12.000000, 13.000000, 14.000000, 15.000000, 16.000000, 17.000000, 18.000000, 19.000000, 20.000000
    };
    float output[20] = {0};

    blurtwo(v, 4, 5, output);

    // Print output
    for (int i = 0; i < 20; i++) {
        printf("%f ", output[i]);
        if ((i + 1) % 10 == 0) printf("\n");
    }
    printf("\n");

    return 0;
}
```

**Output:**

```
14.000000 24.000000 30.000000 22.000000 33.000000 54.000000 63.000000 45.000000 57.000000 90.000000 
99.000000 69.000000 81.000000 126.000000 135.000000 93.000000 62.000000 96.000000 102.000000 70.000000 
```

### Example 2: Im2col with Multiple Arrays

**Function signature:**

```c
void im2col(float* x, float* w, int RR, int W, int K, int B, int A, float* output);
```

**Input data:**

`test_x.json`:

```json
[[1, 2, 3], [4, 5, 6], [7, 8, 9]]
```

`test_w.json`:

```json
[[1.5, 2.5], [3.5, 4.5]]
```

**Command:**

```bash
./wrap.py im2col 2 3 2 1 1 @test_x.json @test_w.json --output-size 12 --run
```

**Generated wrapper** (`wrapper_im2col.c`):

```c
#include "im2col.h"
#include <stdio.h>

int main() {
    float x[9] = {
        1.000000, 2.000000, 3.000000, 4.000000, 5.000000, 6.000000, 7.000000, 8.000000, 9.000000
    };
    float w[4] = {
        1.500000, 2.500000, 3.500000, 4.500000
    };
    float output[12] = {0};

    im2col(x, w, 2, 3, 2, 1, 1, output);

    // Print output
    for (int i = 0; i < 12; i++) {
        printf("%f ", output[i]);
        if ((i + 1) % 10 == 0) printf("\n");
    }
    printf("\n");

    return 0;
}
```

## Type Checking

The tool validates argument counts and types:

```bash
# Error: Wrong number of int arguments
./wrap.py blurtwo 4 @input.json --output-size 20
# Output: Error: Expected 2 int arguments, got 1

# Error: Wrong number of array arguments
./wrap.py im2col 2 3 2 1 1 @test_x.json --output-size 12
# Output: Error: Expected 2 array arguments, got 1
```

## How It Works

1. **Header Parsing**: Scans `*.h` files in library directory, extracts function signatures
2. **Argument Parsing**: Separates numeric args from `@file.json` array args
3. **Type Checking**: Validates argument count matches function signature
4. **JSON Loading**: Loads and flattens nested JSON arrays
5. **Code Generation**: Generates C program with:
   - Static array initialization (no malloc/calloc)
   - Function call with proper arguments
   - Output printing loop
6. **Compilation**: Links with `libscheds.a` using clang
7. **Execution**: Runs wrapper and displays output

## Implementation Details

### Architecture

- **HeaderParser**: Regex-based C header parser, extracts `return_type name(params)`
- **ArrayLoader**: JSON loader with recursive flattening
- **WrapperGenerator**: C code generator using f-string templates
- **Type System**: Maps `float*` → arrays, `int` → scalars, identifies output by name

### Static Allocation Strategy

Generated wrappers use **VLAs (Variable-Length Arrays)** for all data:

```c
float input[20] = {1.0, 2.0, ...};  // Input with initializer
float output[N] = {0};              // Output zero-initialized
```

No heap allocation (`malloc`/`calloc`) required - matches VLA transformation strategy from `replace_calloc.py`.

### Output Size Problem

The tool requires explicit `--output-size` because:

- Output dimensions often depend on complex tensor math
- Inferring from function signatures is unreliable
- Conservative allocation would waste memory
- Explicit size gives user control and clarity

Future enhancement: Parse ATL source to infer output sizes symbolically.

## Available Functions

Run to see all 23 available functions:

```bash
./wrap.py nonexistent 0 --output-size 1
```

Functions include:

- **Blur operations**: `blurtwo`, `blurim`, `blurpart`, `blurisolate`, `blurtiles`, `blurtwopart`
- **Convolutions**: `conv1`, `conv4`, `im2col`, `im2collifted`
- **Matrix operations**: `matmul`, `matmul_tiled`, `matmul_tiled_split`
- **Tensor operations**: `tensoradd`, `tensoradd_split`
- **Data movement**: `gather`, `scatter`
- **Fusion tests**: `fusion_nb`
- **Concatenation tests**: `concattest0-4`

## Troubleshooting

**Compilation fails:**

- Ensure you're in the `stringify/lib/` directory
- Check that `libscheds.a` exists (run `make lib` if needed)

**JSON parse error:**

- Validate JSON syntax (use `jq . file.json`)
- Ensure all values are numeric

**Wrong output size:**

- Check function documentation for output dimensions
- Use conservative overestimate if unsure

**Function not found:**

- Ensure `.h` file exists in library directory
- Check function name spelling

## Integration with Build System

The wrapper generator complements existing tools:

- **replace_calloc.py**: Transforms verified code to VLAs
- **wrap.py**: Generates test harnesses with VLAs
- **make test**: Runs equivalence tests

Workflow:

```bash
cd src/verified_lowering/stringify
make lib                    # Generate C code
python3 lib/replace_calloc.py lib -i   # Transform to VLAs
cd lib
./wrap.py blurtwo 4 5 @input.json --output-size 20 --run  # Test
```

## Technical Notes

- **C99 required**: Uses VLAs (Variable-Length Arrays)
- **Compiler**: Tested with clang, should work with gcc
- **Precision**: Generates `float` arrays (matches ATL `TensorElem R`)
- **Output format**: Space-separated values, 10 per line
- **Memory**: Stack allocation only (no heap)

## Future Enhancements

1. **Symbolic output size inference**: Parse ATL source to compute output dimensions
2. **Batch testing**: Run multiple input files at once
3. **Performance timing**: Add `--benchmark` flag for timing measurements
4. **Output comparison**: Compare against expected results from JSON
5. **Pretty printing**: Format matrix outputs with proper alignment

## See Also

- `README_VLA.md`: VLA transformation documentation
- `VLA_QUICKREF.md`: Quick reference for VLA workflow
- `.github/copilot-instructions.md`: AI agent coding guide
