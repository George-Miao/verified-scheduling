# Verified ATL: Practical Tooling Summary

This document summarizes the pragmatic tooling added to complement the verified ATL compiler.

## Overview

Two Python tools were created to enhance the development workflow without modifying the verified Coq proofs:

1. **VLA Transformation** (`replace_calloc.py`) - Post-processor for memory allocation
2. **CLI Wrapper Generator** (`wrap.py`) - Test harness generator for library functions

Both tools maintain the verified core while adding practical conveniences for C code generation and testing.

---

## Tool 1: VLA Transformation (replace_calloc.py)

### Purpose

Transform heap-allocated intermediate arrays to stack-allocated VLAs (Variable-Length Arrays).

### Motivation

The verified lowering compiler uses `calloc()` for intermediate arrays from `tlet` bindings. While correct, heap allocation is unnecessary for temporaries with known sizes at compile time.

### Approach

**Unverified post-processor** that mechanically transforms generated C code:

- `float *x = calloc(n, sizeof(float));` → `float x[n];`
- Removes corresponding `free(x);` calls
- Applied **after** verification, preserving verified correctness

### Usage

```bash
cd src/verified_lowering/stringify/lib
python3 replace_calloc.py . -i  # Transform all C files in-place
```

### Results

- **Files processed**: 23
- **Transformations**: 6 functions (blurtwo, blurtiles, blurtwopart, conv1, im2col, im2collifted)
- **Test coverage**: 16/16 equivalence tests pass
- **Compilation**: Zero warnings with `clang -Wall -O3`

### Trade-offs

- ✅ Simple mechanical transformation
- ✅ No changes to verified proofs
- ✅ Validated by existing test suite
- ⚠️ Transformation itself is unverified
- ⚠️ Requires C99 compiler support

### Documentation

- Technical details: `src/verified_lowering/stringify/lib/README_VLA.md`
- Quick reference: `VLA_QUICKREF.md`

---

## Tool 2: CLI Wrapper Generator (wrap.py)

### Purpose

Generate standalone C test programs for library functions with CLI-provided arguments.

### Motivation

Testing ATL functions requires:

- Writing boilerplate C code with array initialization
- Manual compilation with correct linking
- Repetitive setup for each test case

The wrapper generator automates this entire workflow.

### Features

1. **Header parsing**: Scans `.h` files, extracts function signatures (23 functions)
2. **Type checking**: Validates CLI arguments match function parameters
3. **JSON loading**: Loads arrays from JSON files, flattens nested structures
4. **Code generation**: Creates standalone C with static VLA initialization
5. **Compilation**: Links with `libscheds.a`, optionally runs tests

### Usage

**Basic wrapper generation:**

```bash
./wrap.py blurtwo 4 5 @input.json --output-size 20
```

**Generate, compile, and run:**

```bash
./wrap.py blurtwo 4 5 @input.json --output-size 20 --run
```

**Multiple array inputs:**

```bash
./wrap.py im2col 2 3 2 1 1 @x.json @w.json --output-size 12 --run
```

### Interface Design

**Syntax:**

```
./wrap.py [function] int_arg1 int_arg2 ... @array1.json @array2.json --output-size N
```

**Argument types:**

- Integers: Passed as-is (e.g., `4`, `5`)
- Arrays: JSON files prefixed with `@` (e.g., `@input.json`)
- Output size: Explicit `--output-size` flag

**JSON format** (nested arrays auto-flattened):

```json
[[1.0, 2.0, 3.0],
 [4.0, 5.0, 6.0],
 [7.0, 8.0, 9.0]]
```

### Generated Code Example

**Input command:**

```bash
./wrap.py blurtwo 4 5 @input.json --output-size 20
```

**Generated `wrapper_blurtwo.c`:**

```c
#include "blurtwo.h"
#include <stdio.h>

int main() {
    float v[20] = {
        1.000000, 2.000000, 3.000000, 4.000000, 5.000000,
        6.000000, 7.000000, 8.000000, 9.000000, 10.000000,
        11.000000, 12.000000, 13.000000, 14.000000, 15.000000,
        16.000000, 17.000000, 18.000000, 19.000000, 20.000000
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

### Implementation Architecture

**HeaderParser**: Regex-based C parser

- Pattern: `(void|int|float) func_name(params);`
- Extracts return type, name, parameter list
- Builds function registry from all `.h` files

**ArrayLoader**: JSON processor

- Recursive flattening for nested arrays
- Validates all elements numeric
- Returns `List[float]` ready for C initialization

**WrapperGenerator**: C code emitter

- Template-based generation with f-strings
- Static VLA declarations with initializers
- Output printing loop (10 values per line)

**Type System**:

- `float*` parameters → array arguments
- `int` parameters → numeric CLI arguments
- Identifies output by name (`output`, case-insensitive)

### Type Checking

The tool validates argument compatibility:

```bash
# Error: Wrong number of int arguments
$ ./wrap.py blurtwo 4 @input.json --output-size 20
Error: Expected 2 int arguments, got 1

# Error: Wrong number of array arguments
$ ./wrap.py im2col 2 3 2 1 1 @x.json --output-size 12
Error: Expected 2 array arguments, got 1
```

### Available Functions (23 total)

**Discovered by scanning `lib/*.h`:**

- Blur operations: `blurtwo`, `blurim`, `blurpart`, `blurisolate`, `blurtiles`, `blurtwopart`
- Convolutions: `conv1`, `conv4`, `im2col`, `im2collifted`
- Matrix operations: `matmul`, `matmul_tiled`, `matmul_tiled_split`
- Tensor operations: `tensoradd`, `tensoradd_split`
- Data movement: `gather`, `scatter`
- Fusion: `fusion_nb`
- Concatenation: `concattest0`, `concattest1`, `concattest2`, `concattest3`, `concattest4`

### Testing Results

**Three test cases validated:**

1. **blurtwo** (simple: 2 ints, 1 array)
   - Input: 4×5 matrix (20 elements)
   - Output: 20-element blurred result
   - Status: ✓ Compiles and runs correctly

2. **im2col** (complex: 5 ints, 2 arrays)
   - Input: 3×3 matrix x, 2×2 weights w
   - Output: 12-element column representation
   - Status: ✓ Compiles and runs correctly

3. **tensoradd** (4 ints, 2 arrays)
   - Input: Two 20-element arrays with dimensions 2×2×5×1
   - Output: 20-element element-wise sum
   - Status: ✓ Compiles and runs correctly

### Documentation

- Complete guide: `src/verified_lowering/stringify/lib/WRAPPER_GUIDE.md`
- Quick reference: `VLA_QUICKREF.md` (updated with wrapper examples)

---

## Integration with Verified Workflow

### Development Cycle

**1. Coq Development** (verified):

```bash
cd src
make examples  # Build ATL optimizations
make low       # Build verified lowering
```

**2. C Code Generation** (verified):

```bash
cd verified_lowering/stringify
make lib       # Generate C from Coq proofs
```

**3. VLA Transformation** (unverified post-process):

```bash
cd lib
python3 replace_calloc.py . -i  # Transform calloc → VLA
```

**4. Testing** (wrapper + existing tests):

```bash
# Existing equivalence tests
cd ..
make test      # 16 tests comparing schedules

# Ad-hoc testing with wrapper
cd lib
./wrap.py blurtwo 4 5 @input.json --output-size 20 --run
./wrap.py im2col 2 3 2 1 1 @x.json @w.json --output-size 12 --run
```

### Verification Boundaries

```
┌─────────────────────────────────────────────────────┐
│ VERIFIED: Coq Proofs + Lowering Correctness        │
│  - ATL language semantics                          │
│  - Scheduling transformations (rw tactics)         │
│  - Lowering to imperative code (ATLDeep)          │
│  - Memory model correctness (heap, stack)          │
└─────────────────────────────────────────────────────┘
                        ↓
           C code generation (Ltac stringify)
                        ↓
┌─────────────────────────────────────────────────────┐
│ UNVERIFIED: Post-processing & Testing               │
│  - replace_calloc.py: calloc → VLA transform       │
│  - wrap.py: test harness generation                │
│  - make test: equivalence testing                   │
└─────────────────────────────────────────────────────┘
```

**Pragmatic approach**:

- Keep verification for complex correctness proofs
- Use testing for simple mechanical transformations
- Maintain clear boundaries between verified/unverified

---

## Design Decisions

### Why Unverified Post-Processor?

**Alternative**: Modify verified compiler to generate VLAs directly

**Challenges**:

- Rewrite memory model in `ATLDeep.v` (heap, stack, allocations)
- Re-prove lowering correctness theorem in `Correct.v`
- Update all allocation-related proofs
- Estimated effort: **months of Coq development**

**Chosen approach**: Unverified transformation

- Mechanical string replacement (low risk)
- No proof modifications required
- Validated by comprehensive test suite
- Pragmatic engineering trade-off

### Why Explicit --output-size?

**Alternative**: Infer output size from function signatures

**Challenges**:

- Output dimensions depend on complex tensor math
- No simple relationship between inputs and output size
- Function signatures don't encode dimensional constraints
- Conservative allocation wastes memory

**Chosen approach**: Explicit size flag

- User specifies exact output dimensions
- Clear and unambiguous
- Allows for experimentation
- Matches ATL's type-level dimension tracking

**Future enhancement**: Parse ATL source to compute output sizes symbolically

---

## Files Created/Modified

### New Files

1. `src/verified_lowering/stringify/lib/replace_calloc.py` (181 lines)
   - VLA transformation engine
   - CLI with argparse
   - In-place and preview modes

2. `src/verified_lowering/stringify/lib/wrap.py` (280+ lines)
   - Header parser (regex-based)
   - JSON array loader with flattening
   - C code generator (f-string templates)
   - CLI with argparse (--compile, --run)

3. `src/verified_lowering/stringify/lib/README_VLA.md`
   - Technical documentation for VLA transformation
   - Usage examples, test results, trade-offs

4. `src/verified_lowering/stringify/lib/WRAPPER_GUIDE.md`
   - Complete wrapper generator guide
   - Examples, type checking, troubleshooting

5. `VLA_QUICKREF.md` (project root)
   - One-page quick reference
   - Commands, test results, affected files

6. `PRAGMATIC_TOOLS.md` (this file)
   - Overview of both tools
   - Integration guide, design decisions

### Updated Files

1. `.github/copilot-instructions.md`
   - Added VLA transformation section
   - Added wrapper generator section
   - Updated code generation pipeline docs

2. `TODO.md`
   - Task 1: VLA transformation (COMPLETED ✅)
   - Task 2: CLI wrapper generator (COMPLETED ✅)

### Modified During Development

- 6 C files in `stringify/lib/` (VLA-transformed)
  - `blurtwo.c`, `blurtiles.c`, `blurtwopart.c`
  - `conv1.c`, `im2col.c`, `im2collifted.c`

### Test Artifacts

- `test_input.json` - 4×5 matrix for blurtwo tests
- `test_x.json` - 3×3 matrix for im2col
- `test_w.json` - 2×2 weights for im2col
- `wrapper_blurtwo.c`, `wrapper_im2col.c`, `wrapper_tensoradd.c` - Generated wrappers

---

## Statistics

### VLA Transformation

- **Files scanned**: 23
- **Files transformed**: 6 (26%)
- **calloc calls replaced**: 6
- **free calls removed**: 6
- **Test coverage**: 16/16 tests pass (100%)
- **Compilation warnings**: 0

### Wrapper Generator

- **Functions discovered**: 23 (from header parsing)
- **Test cases created**: 3 (blurtwo, im2col, tensoradd)
- **Successful compilations**: 3/3 (100%)
- **Type checking errors caught**: 2 (during testing)

---

## Future Enhancements

### VLA Transformation

1. Support other memory patterns (realloc, custom allocators)
2. Add transformation statistics to output
3. Detect and warn about VLA size limits (stack overflow risk)

### Wrapper Generator

1. **Symbolic size inference**: Parse ATL source to compute output dimensions
2. **Batch testing**: Run multiple JSON inputs sequentially
3. **Performance timing**: Add --benchmark flag for timing
4. **Output validation**: Compare against expected results from JSON
5. **Pretty printing**: Format matrix outputs with proper alignment
6. **Random input generation**: Generate test inputs automatically
7. **Code coverage**: Track which functions have test cases

### Integration

1. Add `make wrap-test` target to run wrapper tests
2. CI/CD integration for both tools
3. Bisect debugging with wrapper-generated tests
4. Performance regression testing

---

## Conclusion

Both tools demonstrate **pragmatic engineering** within a verification framework:

**Philosophy**:

- Keep verification where it matters (correctness-critical transformations)
- Use testing where it's sufficient (mechanical transformations, I/O)
- Maintain clear boundaries between verified and unverified code

**Impact**:

- **VLA transformation**: Improves generated code quality without proof changes
- **Wrapper generator**: Streamlines testing workflow, enables rapid experimentation
- **Both**: Complement verified core without compromising soundness

**Validation strategy**:

- Comprehensive test suite (16 equivalence tests)
- Type safety (header parsing, argument validation)
- Manual inspection (generated code review)
- Clear documentation of verification boundaries

This approach balances **formal guarantees** (verified scheduling + lowering) with **practical usability** (clean C code, easy testing), making the ATL framework more accessible and maintainable.
