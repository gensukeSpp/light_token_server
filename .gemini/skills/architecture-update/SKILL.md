---
name: architecture-update
description: Generates high-level architecture snapshots comparing the current branch with main and documents them in docs/architecture.
---
# Skill: Architecture Update
...
This skill automates the process of generating high-level architecture snapshots for the project.

## Workflow

1. **Identify Changes:**
   - Use `invoke_agent` with the `codebase_investigator` to:
     - Determine the base branch (usually `origin/main`).
     - Run `gh pr view` to fetch PR details if the current branch is part of a Pull Request.
     - Analyze the diff to deeply understand the changes and their impact.
     - Identify changed source code files compared to the base branch.
     - List commits between base and current head.

2. **Generate Snapshot:**
   - Create a new file in `docs/architecture/` with the current date: `YYYY-MM-DD-architecture.md`.
   - Populate with:
     - Purpose (Brief explanation of changes).
     - Overview (Purpose, key shifts, core components changed. For SRP refactoring, limit to one line).
     - Dataflow (If applicable).
     - Key design decisions.
     - Next steps/improvements.
     - Commits list.
     - Changed files list.

3. **Update Registry:**
   - Update `docs/architecture/README.md` to include the new entry in the table.

## Usage
Run this skill when major architectural changes are committed to the codebase to maintain up-to-date documentation.
