# BDB Tools — Documentation Update Guide

Quick reference for keeping project docs current as features are added or changed.

---

## When to Update

| Trigger | Files to Update |
|---------|----------------|
| **New feature added** | PLAN.md, README.md, ARCHITECTURE.md (if new routes/tables) |
| **New blueprint/route** | ARCHITECTURE.md, CODE_REFERENCE.md, REUSABLE_COMPONENTS.md (if new pattern) |
| **New database table or column** | ARCHITECTURE.md (schema section) |
| **New reusable pattern** (template partial, JS helper, DB function) | REUSABLE_COMPONENTS.md, CODE_REFERENCE.md |
| **Bug fix or refactor** | Usually none, unless it changes behavior documented in README.md |
| **Feature planned/in progress** | PLAN.md only |
| **Dependency or infra change** | README.md (setup section), ARCHITECTURE.md |

---

## File-by-File Guide

### PLAN.md
**Purpose:** Project roadmap — what's done, what's in progress, what's next.
**Length:** ~260 lines
**Location:** Root

**Structure:**
```
# BDB Tools — Project Plan & Roadmap
## Current State (as of [Month Year])     ← Update the date
## Completed Features                     ← Move features here when done
  ### [Category]                          ← Group by module
  - [x] Feature description
## In Progress                            ← Active work
## Planned / Next Up                      ← Future work
## Backlog                                ← Ideas, low priority
```

**When adding a new feature:**
1. Move it from "Planned" or "In Progress" to "Completed Features" under the right category
2. Use `- [x]` checkbox format to match existing entries
3. Update the "Current State" date and summary paragraph if it's a significant addition

**When planning a new feature:**
1. Add it under "Planned / Next Up" or "In Progress" with a brief description
2. Include any dependencies or prerequisites

**Example entry:**
```markdown
- [x] Backup system with tiered NVMe + TrueNAS strategy and ntfy monitoring
```

---

### README.md
**Purpose:** Public-facing project overview — what the app does, how to set it up, how to run it.
**Length:** ~970 lines
**Location:** Root

**Structure:**
```
# BDB Tools
[One-paragraph summary]
## Features                    ← User-facing feature list grouped by module
  **Module Name**
  - Feature bullet points
## Tech Stack
## Setup / Installation
## Environment Variables
## Running
## Deployment
```

**When adding a new feature:**
1. Add bullet points under the appropriate module in **Features**
2. If it's a new module, add a new `**Module Name**` section in the same style
3. Keep descriptions user-facing — what it does, not how it's coded
4. Don't include implementation details (that goes in ARCHITECTURE.md)

**When adding a new dependency or env var:**
1. Add to **Tech Stack** if it's a major dependency
2. Add to **Environment Variables** section with description

**Style rules:**
- Bold module names: `**Timekeeper**`
- Bullet points for features, not checkboxes (this isn't a roadmap)
- Keep it scannable — one line per feature

**Example:**
```markdown
**Backup System**
- Tiered backup: every 15 minutes to local NVMe, nightly to NVMe + TrueNAS
- SQLite safe atomic backup (no corruption during live use)
- Push notifications via ntfy for failures and daily status reports
```

---

### ARCHITECTURE.md
**Purpose:** Technical deep dive — how the system works, request lifecycle, auth model, database schema, file structure.
**Length:** ~508 lines
**Location:** Root

**Structure:**
```
# BDB Tools — Technical Architecture
## Overview
## Request Lifecycle            ← ASCII diagram of request flow
## Application Entry Point      ← app.py responsibilities
## Authentication & Authorization
## Blueprint / Route Map        ← Table of all blueprints and their routes
## Database                     ← Schema, migration pattern, connection pattern
  ### Schema                    ← All tables with columns
  ### Migration Pattern         ← _add_column_if_missing
## Background Processing        ← task_queue.py
## File Storage                 ← Where uploads go
## Security
## Deployment
```

**When adding a new blueprint:**
1. Add a row to the **Blueprint / Route Map** table:
   ```
   | my_bp | `/admin/my-page` | My feature description |
   ```
2. List key routes with HTTP methods

**When adding a new database table:**
1. Add the full schema under **Database → Schema**:
   ```sql
   CREATE TABLE my_table (
       id INTEGER PRIMARY KEY,
       token TEXT NOT NULL,
       name TEXT NOT NULL,
       created_at TEXT
   );
   ```
2. Note any foreign keys or special columns

**When adding a new column to an existing table:**
1. Update the table's schema listing
2. Note it uses `_add_column_if_missing` for migration

**When adding a new background task:**
1. Add to the **Background Processing** section
2. Document what triggers it and what it produces

**When changing the request flow (middleware, auth, etc.):**
1. Update the ASCII diagram in **Request Lifecycle**
2. Update the **Authentication & Authorization** section if roles change

---

### CODE_REFERENCE.md
**Purpose:** Copy-paste snippets for common patterns. The "cookbook" — how to do things in this codebase.
**Length:** ~757 lines
**Location:** Root

**Structure:**
```
# BDB Tools — Code Reference
## Database — Common Query Patterns
  ### Get all active records for a company
  ### Get single record by ID
  ### Create with audit timestamp
  ### Update with _SENTINEL pattern
  ### Toggle active/inactive
  ### Safe column migration
## Routes — Common Patterns
  ### Admin page with token selector
  ### Employee page with session auth
  ### POST handler with CSRF
  ### JSON API endpoint
## Templates — Common Patterns
  ### Admin page layout
  ### Employee page layout
  ### Form with CSRF token
  ### Searchable select dropdown
## JavaScript — Common Patterns
  ### Fetch with CSRF
  ### Confirm before destructive action
```

**When adding a new pattern:**
1. Add under the appropriate category (Database, Routes, Templates, JavaScript)
2. Include a descriptive heading (`### What this does`)
3. Include a complete, working code snippet pulled from or matching production code
4. Add a brief comment explaining when to use it

**When an existing pattern changes:**
1. Update the snippet to match the new code
2. Note if the old pattern is deprecated

**Style rules:**
- Every snippet should be self-contained and copy-pasteable
- Use actual table/column names from the project as examples
- Include the `conn.close()` — don't leave it as an exercise
- Mark any function parameters that use `_SENTINEL` pattern

**Example new entry:**
```markdown
### Send ntfy push notification
```python
import subprocess
def notify(title, message, topic="your-topic", priority="4"):
    subprocess.run([
        "curl", "-s",
        "-H", f"Title: {title}",
        "-H", f"Priority: {priority}",
        "-d", message,
        f"ntfy.sh/{topic}"
    ], capture_output=True)
```
```

---

### REUSABLE_COMPONENTS.md
**Purpose:** Reference for patterns, partials, helpers, and conventions used across the codebase. The "don't reinvent this" file.
**Length:** ~504 lines
**Location:** Root

**Structure:**
```
# BDB Tools — Reusable Components & Patterns
## Blueprint Pattern             ← How to create a new blueprint
## Database Connection Pattern   ← get_db(), conn.close()
## Authentication Patterns       ← @login_required, _verify_token_access, etc.
## Template Partials             ← _nav.html, _token_selector.html, etc.
## CSS Components                ← Card styles, form styles, button classes
## JavaScript Utilities          ← Searchable select, fetch helpers, etc.
## Employee Access Flags         ← How feature gates work
## Color Scheme System           ← How brand colors propagate
```

**When adding a new reusable component:**
1. Add a section with:
   - **What it is** — one-line description
   - **Where it lives** — file path
   - **How to use it** — code example showing integration
   - **What it replaces** — what NOT to build from scratch

**When adding a new template partial:**
1. Add under **Template Partials** with:
   - File path
   - What variables it expects
   - Include example: `{% include "partials/_my_partial.html" %}`

**When adding a new CSS component:**
1. Add under **CSS Components** with:
   - Class name(s)
   - What it looks like (brief description)
   - Example HTML markup

**When adding a new JS utility:**
1. Add under **JavaScript Utilities** with:
   - Function name and file location
   - Parameters and return value
   - Example call

**Style rules:**
- Always include file paths so readers can find the source
- Show the minimal code needed to use the component
- If a component replaces a common pattern, say so explicitly

---

## Doc Update Checklist

Use this after completing any feature. Copy and check off what applies:

```
Feature: _______________
Date: _______________

[ ] PLAN.md — moved to Completed, updated date
[ ] README.md — added feature bullets under correct module
[ ] ARCHITECTURE.md — added routes/tables/schema changes
[ ] CODE_REFERENCE.md — added new copyable patterns
[ ] REUSABLE_COMPONENTS.md — documented new reusable parts
[ ] Committed doc updates
```

---

## Tips

- **Update docs in the same commit as the feature** — prevents drift
- **Don't duplicate** — ARCHITECTURE.md has the schema, CODE_REFERENCE.md has the snippets, REUSABLE_COMPONENTS.md has the patterns. Each file has one job.
- **Keep README.md user-facing** — a new developer or stakeholder reads this first. Save implementation details for the other files.
- **PLAN.md is the only file with checkboxes** — it's a roadmap. Other files are reference docs.
- **When in doubt, ask**: "Would someone adding a new feature need to know this?" If yes, it belongs in one of these files.
