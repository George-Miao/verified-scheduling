# Quick Reference: VLA Transformation

## One-line command to transform generated C code

```bash
cd src/verified_lowering/stringify/lib && python3 replace_calloc.py . -i
```

## Full workflow: Regenerate and transform

```bash
cd src/verified_lowering/stringify
make clean
make lib                              # Generate C files from Coq
python3 lib/replace_calloc.py lib -i  # Transform calloc → VLA
make test                             # Verify correctness
```

## What happens

**Before transformation:**

```c
float *x = calloc((N + 2) * M, sizeof(float));
// ... code using x ...
free(x);
```

**After transformation:**

```c
float x[(N + 2) * M];  // VLA on stack
// ... code using x ...
// x auto-freed (VLA)
```

## Test results

All 16 equivalence tests pass:

- blurim_blurtiles ✓
- blurim_blurtwo ✓
- blurpart_blurim ✓
- blurpart_blurisolate ✓
- blurtwopart_blurtwo ✓
- concattest0-4_id ✓
- conv4_conv1 ✓
- gather_scatter ✓
- im2collifted_im2col ✓
- matmul_* ✓
- tensoradd_* ✓

## Statistics (current codebase)

- Files processed: 23
- calloc() replaced: 6
- free() removed: 6
- Compile warnings: 0
- Test failures: 0

## Files affected

- `blurtwo.c` - Two-stage blur
- `blurtiles.c` - Tiled blur
- `blurtwopart.c` - Partitioned blur
- `conv1.c` - Convolution
- `im2col.c` - Im2col transformation
- `im2collifted.c` - Lifted im2col

## Testing with CLI Wrapper

Generate test programs for library functions:

```bash
cd src/verified_lowering/stringify/lib
./wrap.py blurtwo 4 5 @input.json --output-size 20 --run
./wrap.py im2col 2 3 2 1 1 @x.json @w.json --output-size 12 --run
```

See `WRAPPER_GUIDE.md` for complete usage guide.

## Documentation

- Full docs: `src/verified_lowering/stringify/lib/README_VLA.md`
- Wrapper guide: `src/verified_lowering/stringify/lib/WRAPPER_GUIDE.md`
- Script: `src/verified_lowering/stringify/lib/replace_calloc.py`
- Wrapper script: `src/verified_lowering/stringify/lib/wrap.py`
- Copilot instructions: `.github/copilot-instructions.md`
- TODO status: `TODO.md` (both tasks completed)
