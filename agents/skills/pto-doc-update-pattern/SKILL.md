---
name: PTO instruction document update mode
description: Summary of document files and location modes that need to be updated when adding new instructions to PTO ISA. Dynamically select the assembly file that needs to be modified based on the classification in docs/assembly/README.md. Trigger: When the document needs to be updated synchronously after adding a new PTO instruction (such as TPOW, TPOWS).
license: CANN Open Software License Agreement Version 2.0
---

# PTO instruction document update mode

This skill summarizes the documentation files and location patterns that need to be updated when adding new instructions (such as TPOW, TPOWS) to the PTO ISA.

## Applicable scenarios

After adding a PTO instruction, use this skill when related documents need to be updated simultaneously. Use `git status` to view the current staging file list to confirm all files that need to be modified.

## Git Staged file classification

### Add new files (need to be created in advance)

| Type | Description |
|------|------|
| Command diagrams | `docs/figures/isa/{command name}.svg` - Command operation diagram |
| Command documentation | `docs/isa/{command name}.md` - Detailed command documentation (English) |
| Instruction document | `docs/isa/{instruction name}_zh.md` - Detailed instruction document (Chinese) |

### Modify files (need to be updated simultaneously)

| Type | Description |
|------|------|
| ISA Master Index | `docs/PTOISA.md` - ISA Index Table |
| ISA Master Index | `docs/PTOISA_zh.md` - ISA Index Table (Chinese) |
| ISA Reference Directory | `docs/isa/README.md` - List of instructions sorted by category |
| ISA Reference Directory | `docs/isa/README_zh.md` - List of instructions sorted by category (Chinese) |
| Menu documentation | `docs/menu_apis.md` - Chinese links sorted by category |
| Assembly reference | `docs/assembly/<category>-ops.md` - dynamic selection based on instruction type |
| Instruction family matrix | `docs/mkdocs/src/manual/appendix-d-instruction-family-matrix.md` - Instruction family matrix |
| Instruction Family Matrix | `docs/mkdocs/src/manual/appendix-d-instruction-family-matrix_zh.md` - Instruction Family Matrix (Chinese) |
| include index | `include/README.md` - implementation status table |
| include index | `include/README_zh.md` - Implementation status table (Chinese) |

---

## Dynamically select assembly documents

Determine the assembly file that needs to be modified according to **### 2. PTO Tile Operation Categories** in `docs/assembly/README.md`.

### Assembly file list (corresponding classification)

| Classification | Assembly File | Description |
|------|----------|------|
| Elementwise (Tile-Tile) | `elementwise-ops.md` | tile-tile element-by-element operation |
| Tile-Scalar / Tile-Immediate | `tile-scalar-ops.md` | tile-scalar operations |
| Axis Reduce / Expand | `axis-ops.md` | Axis reduce/expand operations |
| Memory (GM ↔ Tile) | `memory-ops.md` | Memory operations |
| Matrix Multiply | `matrix-ops.md` | Matrix multiplication operation |
| Data Movement / Layout | `data-movement-ops.md` | Data Movement/Layout Operations |
| Complex | `complex-ops.md` | Complex operations |
| Manual Resource Binding | `manual-binding-ops.md` | Manual resource binding operation |
| Scalar Arithmetic | `scalar-arith-ops.md` | Scalar arithmetic operations |
| Control Flow | `control-flow-ops.md` | Control flow operations |
| Auxiliary Functions | `nonisa-ops.md` | Auxiliary function operations |

### Dynamic selection rules

1. **Determine the instruction classification** - View the classification definition in `docs/assembly/README.md`
2. **Select the corresponding file** - Select the corresponding `<category>-ops.md` file according to the classification
3. **Update Count** - Update the count of `**Total Operations:** N` in this file
4. **Add Chapter** - Insert a new instruction chapter after the last instruction in this category

---

## Detailed explanation of update mode

### 1. ISA main index file

#### docs/PTOISA.md / docs/PTOISA_zh.md
- **Position**: Instruction index table
- **Category**:
  - Element-by-element (Tile-Tile) instructions → inserted after `TFMOD`
  - Tile-scalar / Tile-immediate → inserted after `TSUBSC`

#### include/README.md / include/README_zh.md
- **Position**: Implementation status table (in alphabetical order)
- **Category**:
  - TPOW → inserted between `TPRELU` and `TPUT`
  - TPOWS → inserted between `TPUT_ASYNC` and `TQUANT`

### 2. ISA Reference Directory

#### docs/isa/README.md / docs/isa/README_zh.md
- **Position**: List of instructions sorted by category
- **Category**:
  - Elementwise (Tile-Tile) → inserted after `TFMOD`
  - Tile-Scalar / Tile-Immediate → inserted after `TSUBSC`

### 3. Menu documentation

#### docs/menu_apis.md
- **Position**: Chinese link list sorted by category
- **Same as ISA reference directory structure**

### 4. Assembly document (dynamic selection)

Select the corresponding file according to the instruction type:

| Instruction type | Target file | Insertion position |
|----------|----------|----------|
| TPOW (Elementwise) | `elementwise-ops.md` | After TFMOD |
| TPOWS (Tile-Scalar) | `tile-scalar-ops.md` | TSU BSC post |
| TROWSUM (Axis) | `axis-ops.md` | after the last Axis directive |
| TLOAD (Memory) | `memory-ops.md` | After the last Memory instruction |
| TMATMUL (Matrix) | `matrix-ops.md` | after the last Matrix directive |
| TMOV (Data Movement) | `data-movement-ops.md` | After the last Data Movement directive |
| TQUANT (Complex) | `complex-ops.md` | after the last Complex directive |
| TASSIGN (Manual Binding) | `manual-binding-ops.md` | After the last Manual directive |

### 5. Instruction family matrix

#### docs/mkdocs/src/manual/appendix-d-instruction-family-matrix.md
- **Position**: D.2 coverage statistics table + D.4 family matrix table
- **D.2 Update Example**:
  ```
  | Elementwise (Tile-Tile) | 28 → 29 |
  | Tile-Scalar / Tile-Immediate | 19 → 20 |
  | Total | 126 → 128 |
  ```
- **D.4 Update**:
  - Insert new instructions after the last entry of the corresponding category

#### docs/mkdocs/src/manual/appendix-d-instruction-family-matrix_zh.md
- **Same as English version**

---

## Common new instruction classification and insertion location

### Tile-Tile (element-by-element double Tile)
- **INSERT POSITION**: after `TFMOD`
- **Corresponding file**: `elementwise-ops.md`
- **Example**: TPOW

### Tile-Scalar (Tile and scalar)
- **Insert position**: after `TSUBSC`
- **Corresponding file**: `tile-scalar-ops.md`
- **Example**: TPOWS

### Axis Reduce / Expand
- **Insertion position**: after the last Axis directive
- **Corresponding file**: `axis-ops.md`

### Memory (GM ↔ Tile)
- **Insertion position**: after the last Memory instruction
- **Corresponding file**: `memory-ops.md`

---

## Update checklist

### Add new files (pre-created)
- [ ] `docs/figures/isa/{new command}.svg` - Schematic diagram of command operation
- [ ] `docs/isa/{new command}.md` - Detailed command document (English)
- [ ] `docs/isa/{New Command}_zh.md` - Detailed command document (Chinese)

### Modify files (synchronous updates)
- [ ] `docs/PTOISA.md` - ISA main index
- [ ] `docs/PTOISA_zh.md` - ISA Main Index (Chinese)
- [ ] `include/README.md` - include index
- [ ] `include/README_zh.md` - include index (Chinese)
- [ ] `docs/isa/README.md` - ISA reference directory
- [ ] `docs/isa/README_zh.md` - ISA reference directory (Chinese)
- [ ] `docs/menu_apis.md` - Menu documentation
- [ ] `docs/assembly/<category>-ops.md` - dynamically selected assembly file (English + Chinese)
- [ ] `docs/mkdocs/src/manual/appendix-d-instruction-family-matrix.md` - Instruction family matrix
- [ ] `docs/mkdocs/src/manual/appendix-d-instruction-family-matrix_zh.md` - Instruction Family Matrix (Chinese)

---

## Notes

1. **English + Chinese**: Each file has both Chinese and English versions and needs to be updated simultaneously.
2. **Dynamic Selection**: Determine the assembly file that needs to be modified based on the category selected in `docs/assembly/README.md`
3. **Count changes**: Operation Count (category subtotal) and Total (total) need to be updated at the same time
4. **Detailed instruction document**: needs to be created in advance in the `docs/isa/` directory
5. **diagrams**: need to be created in advance in the `docs/figures/isa/` directory
6. Use `git status` to view the current staging file list. This is the best way to confirm all files that need to be modified.