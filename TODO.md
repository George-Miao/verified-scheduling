# TODO List

This file contains a list of planned features, improvements, and tasks for the verified scheduling project. It serves as a roadmap for future development and enhancements.

---

## Task 2: CLI Wrapper Generator for Library Functions

### Goal

Create `wrap.py` script to generate standalone C wrapper programs for testing library functions with arguments passed from CLI.

**Interface:**

```bash
./wrap.py [function_name] arg1 arg2 ... @array1.json @array2.json
```

**Features:**

- Parse function signatures from .h files
- Type-check CLI arguments against function parameters
- Load arrays from JSON files
- Generate C code with static array allocations
- Support both simple (blurtwo) and complex (im2col) functions

### Tasks

#### 1. Design wrapper script architecture and CLI interface

**Status:** Not started

**Requirements:**

- Parse command line: function_name, numeric args (int), array args (@file.json)
- Output: wrapper_[function].c with main() that calls the function
- Clear separation: arg parsing → signature checking → code generation

---

#### 2. Implement header file parser

**Status:** Not started

**File:** `src/verified_lowering/stringify/lib/wrap.py`

**Tasks:**

- Scan lib/*.h files for function declarations
- Parse C function signatures: `void func(float* x, int N, float* output)`
- Extract: return type, function name, parameter types/names
- Build function registry: `{func_name: {params: [...], return_type: ...}}`
- Handle pointer types (float*, float*output treated differently?)

---

#### 3. Implement type checking and argument validation

**Status:** Not started

**Validation rules:**

- Count: #args == #params (excluding output)
- Type match: int param ← numeric arg, float* param ← @array.json
- Special handling for output parameter (last float*)
- Error messages: "Expected int for param 'N', got array @foo.json"

---

#### 4. Implement JSON array parser

**Status:** Not started

**JSON format support:**

```json
[1, 2, 3, 4]              // 1D: size=4
[[1,2], [3,4], [5,6]]     // 2D: size=6 (flattened)
```

**Tasks:**

- Load JSON, validate all numeric
- Flatten nested arrays (C uses row-major)
- Compute total size for static allocation

---

#### 5. Implement static array size computation

**Status:** Not started

**Size inference:**

- Input arrays: size = len(flatten(json_data))
- Output array: TBD strategy
  - Option A: Require explicit --output-size N
  - Option B: Infer from function name heuristics
  - Option C: User provides output shape in JSON

**Generated code:**

```c
float input_v[14] = {1.0, 2.0, ..., 14.0};
float output[10];  // Size TBD
```

---

#### 6. Implement C code generator

**Status:** Not started

**Template structure:**

```c
#include "function.h"
#include <stdio.h>

int main() {
    // Static input arrays with initializers
    float arr1[N] = {...};
    float arr2[M] = {...};

    // Output array
    float output[K];

    // Function call
    function_name(arr1, arr2, param1, param2, output);

    // Print output (for verification)
    for (int i = 0; i < K; i++) {
        printf("%f ", output[i]);
    }
    return 0;
}
```

---

#### 7. Add compilation and execution helpers

**Status:** Not started

**Features:**

- Generate compile command: `clang -I. wrapper.c libscheds.a -o wrapper`
- Optional: Auto-compile with `--compile` flag
- Optional: Auto-run with `--run` flag
- Make script executable

---

#### 8. Test with example functions

**Status:** Not started

**Test cases:**

1. `blurtwo`: Simple (2 ints, 1 array, output)
2. `im2col`: Complex (5 ints, 2 arrays, output)
3. `matmul`: Matrix multiply variant
4. Edge cases: empty arrays, large arrays, type mismatches

**Success criteria:**

- Generated code compiles without warnings
- Execution produces reasonable output
- Type errors are caught before generation

---

#### 9. Create documentation and examples

**Status:** Not started

**Deliverables:**

- Create `WRAPPER_GUIDE.md` with usage examples
- Example JSON files: `examples/blur_input.json`
- Add section to VLA_QUICKREF.md
- Document limitations and assumptions

---

### Implementation Notes

**Output size problem:** Most challenging aspect. Three approaches:

1. **Require explicit size:** `./wrap.py blurtwo 10 20 @input.json --output-size 200`
2. **Parse function internals:** Analyze .c file to infer output size formula
3. **Allocate large buffer:** Use conservative estimate (wasteful but safe)

**Recommendation:** Start with approach #1 (explicit), add #2 later if needed.

---
