import{r as y,j as d,L as x}from"./vendor-react-Ds644eE6.js";import{c as A}from"./vendor-recharts-C58zgzh2.js";import{B as M,br as I,bs as T,H as R}from"./index-CyDMlcSY.js";import{u as E}from"./vendor-i18n-DFJuOPeM.js";import{b as P}from"./vendor-dompurify-ChJSIbGG.js";import"./vendor-flow-BA4JlW4m.js";import"./vendor-query-wpw2X9UX.js";import"./vendor-preload-ckwbz45p.js";import"./i18n-en-GeGxRQLs.js";import"./vendor-dnd-1FmqKfd0.js";function g(t){return t.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}function C(t){return t.toLowerCase().replace(/`/g,"").replace(/[^a-z0-9]+/g,"-").replace(/(^-|-$)/g,"")}function m(t){let n=g(t);return n=n.replace(/`([^`\n]+)`/g,(a,c)=>`<code class="rounded bg-surface-secondary px-1.5 py-0.5 text-[0.85em] font-mono text-oe-blue">${c}</code>`),n=n.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g,(a,c,s)=>{const e=/^https?:\/\//i.test(s),r=s.startsWith("/")||s.startsWith("#"),i=/^mailto:/i.test(s);return!e&&!r&&!i?c:`<a href="${s}"${e?' target="_blank" rel="noopener noreferrer"':""} class="text-oe-blue underline underline-offset-2 hover:opacity-80">${c}</a>`}),n=n.replace(/\*\*([^*]+?)\*\*/g,'<strong class="font-semibold text-content-primary">$1</strong>'),n=n.replace(new RegExp("(?<!\\w)\\*([^*\\n]+?)\\*(?!\\w)","g"),"<em>$1</em>"),n}function f(t){let n=t.trim();return n.startsWith("|")&&(n=n.slice(1)),n.endsWith("|")&&(n=n.slice(0,-1)),n.split(new RegExp("(?<!\\\\)\\|")).map(a=>a.replace(/\\\|/g,"|").trim())}function _(t){return t.includes("|")&&t.trim()!==""}function v(t){const n=t.trim();return!n.includes("-")||!n.includes("|")?!1:f(t).every(a=>/^:?-{1,}:?$/.test(a))}function b(t){return t==="center"?"text-center":t==="right"?"text-right":"text-left"}function S(t,n){const a=f(t[n]??""),c=f(t[n+1]??"").map(o=>{const l=o.startsWith(":"),u=o.endsWith(":");return l&&u?"center":u?"right":"left"}),s=[];let e=n+2;for(;e<t.length&&_(t[e]??"")&&!v(t[e]??"");)s.push(f(t[e]??"")),e+=1;const r=a.length,i=a.map((o,l)=>`<th class="border border-border-light bg-surface-secondary/60 px-3 py-2 font-semibold text-content-primary ${b(c[l]??"left")}">${m(o)}</th>`).join(""),p=s.map(o=>{const l=[];for(let u=0;u<r;u+=1)l.push(`<td class="border border-border-light px-3 py-2 align-top ${b(c[u]??"left")}">${m(o[u]??"")}</td>`);return`<tr>${l.join("")}</tr>`}).join("");return{html:`<div class="my-4 overflow-x-auto"><table class="w-full border-collapse text-sm text-content-secondary"><thead><tr>${i}</tr></thead><tbody>${p}</tbody></table></div>`,next:e}}const j={1:"text-2xl font-semibold mt-2 mb-3",2:"text-xl font-semibold mt-8 mb-3 pb-1.5 border-b border-border-light",3:"text-base font-semibold mt-6 mb-2",4:"text-sm font-semibold uppercase tracking-wide text-content-tertiary mt-4 mb-1"};function D(t){const n=t.replace(/\r\n/g,`
`).replace(/\r/g,`
`).split(`
`),a=[];let c=[];const s=()=>{c.length&&(a.push(`<p class="my-3 leading-relaxed text-content-secondary">${m(c.join(" "))}</p>`),c=[])};let e=0;for(;e<n.length;){const r=n[e]??"",i=r.match(/^```(\w*)\s*$/);if(i){s();const o=i[1]??"",l=[];for(e+=1;e<n.length&&!/^```\s*$/.test(n[e]??"");)l.push(n[e]??""),e+=1;e+=1;const u=g(l.join(`
`)),w=o?`<span class="absolute right-2 top-2 text-2xs uppercase tracking-wider text-gray-400">${g(o)}</span>`:"";a.push(`<pre class="relative my-4 overflow-x-auto rounded-lg border border-border-light bg-gray-900 dark:bg-gray-950 p-4 pt-5 text-xs leading-relaxed font-mono text-gray-100">${w}<code class="whitespace-pre">${u}</code></pre>`);continue}const p=r.match(/^(#{1,4})\s+(.*)$/);if(p){s();const o=(p[1]??"#").length,l=(p[2]??"").trim();a.push(`<h${o} id="${C(l)}" class="scroll-mt-24 text-content-primary ${j[o]??""}">${m(l)}</h${o}>`),e+=1;continue}if(/^(?:-{3,}|\*{3,})\s*$/.test(r)){s(),a.push('<hr class="my-6 border-t border-border-light" />'),e+=1;continue}if(/^>\s?/.test(r)){s();const o=[];for(;e<n.length&&/^>\s?/.test(n[e]??"");)o.push((n[e]??"").replace(/^>\s?/,"")),e+=1;a.push(`<blockquote class="my-4 rounded-r-lg border-l-4 border-oe-blue/40 bg-surface-secondary/40 px-4 py-2.5 text-sm text-content-secondary">${m(o.join(" "))}</blockquote>`);continue}if(_(r)&&v(n[e+1]??"")){s();const o=S(n,e);a.push(o.html),e=o.next;continue}if(/^\s*[-*]\s+/.test(r)){s();const o=[];for(;e<n.length&&/^\s*[-*]\s+/.test(n[e]??"");)o.push((n[e]??"").replace(/^\s*[-*]\s+/,"")),e+=1;const l=o.map(u=>`<li class="my-1">${m(u)}</li>`).join("");a.push(`<ul class="my-3 list-disc space-y-1 pl-6 text-content-secondary">${l}</ul>`);continue}if(/^\s*\d+\.\s+/.test(r)){s();const o=[];for(;e<n.length&&/^\s*\d+\.\s+/.test(n[e]??"");)o.push((n[e]??"").replace(/^\s*\d+\.\s+/,"")),e+=1;const l=o.map(u=>`<li class="my-1">${m(u)}</li>`).join("");a.push(`<ol class="my-3 list-decimal space-y-1 pl-6 text-content-secondary">${l}</ol>`);continue}if(r.trim()===""){s(),e+=1;continue}c.push(r.trim()),e+=1}return s(),P.sanitize(a.join(`
`),{ALLOWED_TAGS:["h1","h2","h3","h4","p","ul","ol","li","pre","code","strong","em","a","blockquote","hr","table","thead","tbody","tr","th","td","span","br"],ALLOWED_ATTR:["id","class","href","target","rel"],ADD_ATTR:["target","rel"]})}function O({source:t,className:n}){const a=y.useMemo(()=>D(t),[t]);return d.jsx("div",{className:n,dangerouslySetInnerHTML:{__html:a}})}const k=`# Build your own module

OpenConstructionERP is built entirely from modules. Every business feature you see (BOQ, BIM Hub, Schedule, CDE, regional packs, AI tooling) is a self-contained module that the platform discovers, loads and mounts on its own. This guide is a practical, ten-minute walkthrough for adding your own.

There are two ways to extend the platform. A **partner pack** is a code-free preset bundle (branding, locale, currency, which modules to show) that anyone can build and share. A **module** is real code: new screens, endpoints, tables, validation rules. Start with the part you need.

---

## Partner Packs

A partner pack is a small, code-free preset bundle for a country, region or company. It carries presets only: branding (logo and colours), a default locale and currency, which modules to show or hide, an optional onboarding script, and references to cost-database regions and validation rule packs that already exist in the core. Anyone can build one, share it, and let an admin activate it in one click from the Partner Packs tab.

> A pack switches on what already exists. It can set a default currency, default and additional languages, which modules are visible, co-branding, an onboarding script, and which built-in CWICR regions and validation rule packs to turn on.

> A pack ships no code and no data. It is declarative only and is never executed. It cannot ship new validation rule classes or its own catalog data; it only references rule packs and cost regions the core already provides. If you need new screens, endpoints, tables or rules, build a module instead.

### 1. Scaffold the pack

The CLI scaffolds a ready-to-edit folder with a valid manifest, a placeholder logo, an onboarding script and a README. Edit the placeholders and you are done, no code to write.

\`\`\`bash
openconstructionerp pack new acme-co
# -> creates acme-co/ with:
#      manifest.json    the pack definition (only required file)
#      logo.svg         your logo, shown in-app
#      onboarding.yaml  optional first-login onboarding script
#      README.md
\`\`\`

Prefer to author it by hand? Just create a folder with a \`manifest.json\`. The minimal shape is below.

### 2. Edit manifest.json

\`manifest.json\` is a serialized PartnerPackManifest. \`slug\`, \`partner_name\` and \`pack_version\` identify the pack; the rest are the presets it applies. An empty \`default_modules\` means all modules stay visible.

\`\`\`json
{
  "slug": "acme-co",
  "partner_name": "ACME Construction",
  "partner_url": "https://acme.example",
  "pack_version": "0.1.0",
  "description": "Preset for ACME teams in the UK.",
  "default_locale": "en",
  "additional_locales": {},
  "cwicr_regions": [],
  "default_currency": "GBP",
  "default_tax_template": null,
  "validation_rule_packs": [],
  "default_modules": [],
  "hidden_modules": [],
  "branding": {
    "primary_color": "#0F2C5F",
    "accent_color": null,
    "logo_path": "logo.svg",
    "favicon_path": null,
    "powered_by_text": null
  },
  "onboarding_script_path": "onboarding.yaml",
  "metadata": {
    "country": "GB",
    "country_name_en": "United Kingdom",
    "support_email": "hello@acme.example"
  }
}
\`\`\`

### 3. Install it (two ways)

Drop the folder (or a \`.zip\` of it) into your install's data directory under \`packs/\`, by default \`~/.openestimate/packs/\` next to the database, then open the Partner Packs tab and click Rescan. No restart needed.

\`\`\`bash
# Drop-in: place the pack beside the database, then Rescan in the app
~/.openestimate/packs/acme-co/manifest.json
\`\`\`

Or zip the folder and upload the \`.zip\` directly on the Partner Packs tab using the in-app installer (admins only). It is extracted into the same \`packs/\` directory and appears immediately.

### 4. Activate it

Open Modules then Partner Packs, find your pack and press Activate. It applies the currency, language, validation standards, module visibility and branding, and can install a demo project. Activation is reversible: Deactivate restores the previous state at any time.

> Packs dropped into the data dir, and packs in the repo \`packs/\` folder, are picked up by Rescan with no restart. Only a brand-new pack shipped as a pip package (registered via an entry point) may still need a backend restart before it appears.

### Optional: ship as a pip package

To distribute on PyPI instead of as a folder or zip, expose the manifest through the entry-point group so it is discovered after \`pip install\`. A pip-installed pack may require a one-time backend restart.

\`\`\`toml
[project.entry-points."openconstructionerp.partner_packs"]
acme-co = "openconstructionerp_acme_co:MANIFEST"
\`\`\`

### Sharing your pack

- Add it as a package to the platform (publish your pip package) so anyone can install and activate it.
- Or contribute it directly through a pull request, which makes it visible to everyone out of the box.
- The pack can display your contact details or website to whoever uses it (your partner website, support email and your co-branding line).
- We can also share information about you and your pack through our social networks, so more people discover your work.

To list your pack or get featured, contact info@datadrivenconstruction.io. A pack holds presets only, no code. If you need new screens, endpoints or tables, build a module (below) and reference it from your pack via \`default_modules\`.

---

## Prerequisites

Have these ready before starting. If you can run the app locally, you already have everything you need.

- **Python 3.12+**: backend runtime
- **Node.js 22+**: frontend build (CI builds on 24)
- **Git**: clone and commit
- **PostgreSQL 16 or SQLite**: SQLite is auto-created in dev
- **An editor**: VS Code, Cursor, or anything with Python + TypeScript support
- **A clone of the repo** to hack on the module

\`\`\`bash
git clone https://github.com/datadrivenconstruction/OpenConstructionERP.git
cd OpenConstructionERP
# Backend
cd backend && pip install -e ".[dev]"
uvicorn app.main:create_app --factory --reload --port 8000
# Frontend (new terminal)
cd frontend && npm install && npm run dev
\`\`\`

Open http://localhost:5173 and log in. Confirm the Modules page loads before starting.

---

## Hello World: your first module in 3 minutes

A minimal end-to-end backend module that serves a greeting endpoint. Copy-paste the blocks below, restart the backend, and curl the route. That is the full loop.

\`\`\`bash
# 1. Create the folder
mkdir -p backend/app/modules/hello_world

# 2. Mark it as a package (empty file)
touch backend/app/modules/hello_world/__init__.py
\`\`\`

\`\`\`python
# 3. backend/app/modules/hello_world/manifest.py
from app.core.module_loader import ModuleManifest

manifest = ModuleManifest(
    name="oe_hello_world",
    version="0.1.0",
    display_name="Hello World",
    description="My first module",
    author="Me",
    category="community",
    depends=[],
    auto_install=True,
    enabled=True,
)
\`\`\`

\`\`\`python
# 4. backend/app/modules/hello_world/router.py
from fastapi import APIRouter

router = APIRouter(prefix="/hello_world", tags=["hello_world"])

@router.get("/")
async def greet(name: str = "World"):
    return {"message": f"Hello, {name}!"}
\`\`\`

\`\`\`bash
# 5. Restart backend (Ctrl+C, re-run uvicorn) and test
curl "http://localhost:8000/api/v1/hello_world/?name=Artem"
# -> {"message":"Hello, Artem!"}
\`\`\`

> That is it: no \`main.py\` edit, no registry import, no migration. The module loader discovers the folder, reads the manifest, and mounts the router. The module also appears under Modules & Marketplace automatically.

---

## What is a module?

Every business feature is a self-contained module. A module can add REST routes, database tables, UI pages, validation rules, translations, or any combination. You can enable, disable, install or replace any module without touching the core.

- **Backend only**: e.g. a new API connector or webhook receiver.
- **Frontend only**: e.g. a regional BOQ-exchange UI or a niche report.
- **Full-stack**: most real features, with routes, UI and a database migration.

---

## Backend module in 5 minutes

Everything starts from the template in the repo. The module loader auto-discovers anything you drop into \`backend/app/modules/\`, with no manual wiring of routes or migrations.

1. **Scaffold from the template.** The Makefile target is the one used in CI examples; a raw copy works on machines without \`make\`.

\`\`\`bash
# Option A - Makefile target (uses the scaffolder script)
make module-new NAME=oe_my_module

# Option B - plain copy of the template
cp -r modules/oe-module-template backend/app/modules/my_module
\`\`\`

2. **Edit the manifest.** Open \`backend/app/modules/my_module/manifest.py\` and set \`name\`, \`version\`, \`display_name\`, and any dependencies on other modules.

\`\`\`python
from app.core.module_loader import ModuleManifest

manifest = ModuleManifest(
    name="oe_my_module",            # unique, snake_case, oe_ prefix
    version="0.1.0",
    display_name="My Module",
    description="One-line description",
    author="Your Name",
    category="community",            # core | integration | regional | community
    depends=["oe_projects"],         # hard deps - load fails without them
    optional_depends=["oe_boq"],     # soft deps - present-if-installed
    display_name_i18n={              # localized display names (optional)
        "de": "Mein Modul",
        "ru": "Мой модуль",
    },
    auto_install=False,              # True = enabled on first boot
    enabled=True,
)
\`\`\`

3. **Add a router.** Routes live in \`router.py\`. The loader mounts the router at \`/api/v1/my_module/*\` automatically; you do not touch \`main.py\`.

\`\`\`python
from fastapi import APIRouter

router = APIRouter(prefix="/my_module", tags=["my_module"])

@router.get("/")
async def list_items():
    return {"items": []}
\`\`\`

4. **Add models and schemas (optional).** Drop SQLAlchemy models into \`models.py\`, Pydantic request/response schemas into \`schemas.py\`. If you add tables, generate an Alembic migration (see below).

5. **Declare validation rules.** Modules that ingest data must ship validation rules. Subclass \`ValidationRule\` in \`backend/app/core/validation/rules/\` and the engine registers it.

6. **Restart and enable.** Restart the backend. The module loader picks up your folder, and the module appears under Modules & Marketplace, System Modules. Toggle it on.

> Reference implementations: \`backend/app/modules/boq/\` and \`backend/app/modules/projects/\`.

---

## File structure: what goes where

Both backend and frontend modules follow a strict convention. Follow it and the loader and registry wire everything up; deviate and things break in surprising places. All files except the manifest are optional; start with the smallest set and add files as the module grows.

\`\`\`text
backend/app/modules/my_module/
├── __init__.py          # empty, marks as package
├── manifest.py          # required: metadata + deps
├── models.py            # SQLAlchemy models (auto-registered)
├── schemas.py           # Pydantic request/response
├── router.py            # FastAPI routes (auto-mounted)
├── service.py           # business logic (stateless)
├── repository.py        # data access layer
├── permissions.py       # permission declarations
├── events.py            # event handlers (optional)
├── hooks.py             # hook handlers (optional)
├── validators.py        # validation rules (optional)
├── migrations/          # Alembic migrations (module-scoped)
│   └── versions/
└── tests/               # pytest
\`\`\`

\`\`\`text
frontend/src/modules/my-feature/
├── manifest.ts          # required: id, routes, navItems
├── MyFeatureModule.tsx  # main React component
├── components/          # sub-components (optional)
├── api.ts               # API client fns (uses shared/lib/api)
├── hooks/               # custom hooks (optional)
├── types.ts             # TS types (optional)
└── __tests__/           # vitest
\`\`\`

---

## Database migrations

If your module adds or changes tables, you must ship a migration. The project uses Alembic; autogenerate is your friend but always review the result.

1. **Define your model.**

\`\`\`python
# backend/app/modules/my_module/models.py
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from app.database import Base

class MyItem(Base):
    __tablename__ = "oe_my_module_item"   # prefix with the module name

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
\`\`\`

2. **Register the model on app startup.** Open \`backend/app/main.py\`, find the \`_import_models_for_migrations\` block, and add one line:

\`\`\`python
from app.modules.my_module import models as _my_module_models  # noqa: F401
\`\`\`

3. **Generate the migration.**

\`\`\`bash
cd backend
alembic revision --autogenerate -m "my_module: initial schema"
# Review alembic/versions/<hash>_my_module_initial_schema.py
alembic upgrade head
\`\`\`

4. **Ship it.** Commit the migration file in \`backend/alembic/versions/\`. On upgrade, existing installs run \`alembic upgrade head\` and pick up your new tables automatically.

> Always prefix table names with the module slug (\`oe_my_module_*\`) to avoid collisions. Never drop columns in a single migration: add the new column, backfill, then drop in a later release.

---

## Frontend module in 5 minutes

Frontend modules live in \`frontend/src/modules/\`. Each exports a manifest that declares routes, nav items and translations. The registry wires them into the sidebar and router automatically.

1. **Create the folder:** \`mkdir frontend/src/modules/my-feature\`.

2. **Create manifest.ts.**

\`\`\`ts
import { lazy } from 'react';
import { Sparkles } from 'lucide-react';
import type { ModuleManifest } from '../_types';

const MyFeatureModule = lazy(() => import('./MyFeatureModule'));

export const manifest: ModuleManifest = {
  id: 'my-feature',
  name: 'My Feature',
  description: 'What this module does in one line',
  version: '1.0.0',
  icon: Sparkles,
  category: 'tools',
  defaultEnabled: false,
  depends: ['boq'],
  routes: [
    { path: '/my-feature', title: 'My Feature', component: MyFeatureModule },
  ],
  navItems: [
    { labelKey: 'nav.my_feature', to: '/my-feature', icon: Sparkles, group: 'tools', advancedOnly: true },
  ],
};
\`\`\`

3. **Build the React page.** Create \`MyFeatureModule.tsx\`, a normal React component. Use \`useTranslation()\` for every user-visible string.

4. **Register it.** Open \`frontend/src/modules/_registry.ts\` and add your import to the \`MODULE_REGISTRY\` array.

\`\`\`ts
import { manifest as myFeature } from './my-feature/manifest';
export const MODULE_REGISTRY = [/* ... */ myFeature];
\`\`\`

5. **Add translations.** Add the English string for every new i18n key to \`frontend/src/app/locales/en\` and provide an inline \`defaultValue\`. Never leave a raw English string in TSX.

---

## Events and hooks: how modules talk to each other

Never import from another module directly. Emit events and subscribe to them. This keeps modules decoupled and makes installing or disabling safe.

\`\`\`python
# Publish an event
from app.core.events import event_bus

await event_bus.publish(
    "my_module.item.created",
    {"item_id": item.id, "name": item.name},
)
\`\`\`

\`\`\`python
# Subscribe in events.py
from app.core.events import event_bus

async def on_boq_change(event):
    # event.payload is the dict from publish()
    ...

event_bus.subscribe("boq.position.updated", on_boq_change)
\`\`\`

Common events you can listen for:

- \`projects.project.created\`: after a project is created
- \`boq.position.created\` / \`.updated\` / \`.deleted\`
- \`users.user.created\` / \`.role_changed\`
- \`documents.document.uploaded\`
- \`bim.model.ingested\`: after CAD/BIM conversion succeeds

---

## Permissions and RBAC

Declare the permissions your module uses. Protect every mutating endpoint with \`RequirePermission\`; never rely on the user being logged in alone.

\`\`\`python
# backend/app/modules/my_module/permissions.py
from app.core.permissions import Role, permission_registry

def register_my_module_permissions() -> None:
    permission_registry.register_module_permissions(
        "my_module",
        {
            "my_module.read":   Role.VIEWER,   # anyone signed in
            "my_module.create": Role.EDITOR,
            "my_module.update": Role.EDITOR,
            "my_module.delete": Role.MANAGER,
        },
    )

register_my_module_permissions()
\`\`\`

\`\`\`python
from fastapi import Depends
from app.dependencies import RequirePermission

@router.post("/items", dependencies=[Depends(RequirePermission("my_module.create"))])
async def create_item(data: CreateItemSchema):
    return await service.create(data)
\`\`\`

> Roles are ordered admin > manager > editor > viewer. Grant a permission to \`Role.EDITOR\` and every editor, manager and admin gets it automatically; admin always bypasses, so you never list it explicitly. Unregistered permission names default to admin-only, which is safe but usually not what you want.

---

## Testing your module

Tests gate every PR. The project uses pytest for backend, vitest for frontend, and Playwright for end-to-end. Running them locally uses the same commands as CI.

\`\`\`bash
# Backend - pytest
pytest backend/app/modules/my_module
pytest backend/tests/integration

# Frontend - vitest
cd frontend
npm run test
npm run typecheck

# End-to-end - Playwright
cd frontend
npx playwright test
\`\`\`

Backend tests use httpx + ASGITransport, with no real HTTP. Frontend tests run in jsdom. Shared integration fixtures live in \`backend/tests/integration/_auth_helpers.py\`.

---

## Installing a third-party module

\`\`\`bash
# Zip install (recommended)
openconstructionerp module install path/to/my-module-1.0.0.zip

# Manual copy (development)
cp -r downloaded-module backend/app/modules/
# restart backend
\`\`\`

Then enable it under Modules & Marketplace, System Modules.

---

## Core rules (enforced in PR review)

1. **i18n everywhere.** Every user-visible string goes through \`t()\`. English strings live in \`frontend/src/app/locales/en\`.
2. **No IfcOpenShell, no native IFC.** CAD/BIM is always converted through DDC cad2data into the canonical JSON format.
3. **Validation is not optional.** Any module that ingests data must declare validation rules.
4. **AI-augmented, human-confirmed.** AI suggestions must show a confidence score and require user confirmation before mutating data.
5. **AGPL-3.0 compliance.** The platform is dual-licensed (AGPL + Commercial). There is no CLA and no external pull requests: modules are distributed as their own packages.

---

## Quick reference

| I need to...                         | Look at...                                                     |
| ------------------------------------ | ------------------------------------------------------------- |
| Scaffold a backend module            | \`modules/oe-module-template/\`                                  |
| Real-world backend example           | \`backend/app/modules/boq/\`                                     |
| Real-world frontend example          | \`frontend/src/modules/pdf-takeoff/\`                            |
| Add validation rules                 | \`backend/app/core/validation/rules/\`                          |
| Hook into events                     | \`backend/app/core/events.py\`                                  |
| Add translations                     | \`frontend/src/app/locales/en\`                                 |
| Declare a permission                 | \`backend/app/modules/my_module/permissions.py\`               |
| Guard an endpoint                    | \`Depends(RequirePermission("my_module.create"))\`             |
| Register a model for migrations      | \`backend/app/main.py\` -> \`_import_models_for_migrations\`      |
| Generate a migration                 | \`alembic revision --autogenerate -m "msg"\`                   |
| Publish an event                     | \`event_bus.publish("my_module.item.created", payload)\`        |
| Subscribe to an event                | \`event_bus.subscribe("boq.position.updated", handler)\`        |
| Run backend tests                    | \`pytest backend/app/modules/my_module\`                        |
| Run frontend typecheck               | \`cd frontend && npm run typecheck\`                            |
| Package module for sharing           | \`zip -r my-module-0.1.0.zip my_module/\`                       |

---

## For AI agents

If you are an AI agent scaffolding a module on behalf of a user, follow the same rules as humans, plus:

- Copy the template; do not invent the manifest schema. It changes faster than any document.
- Before reporting the module done, run \`npm run typecheck\` and \`ruff check\` + \`pytest\`. A green build is the contract.
- Never edit the contract files (\`_types.ts\` or the shape of \`_registry.ts\`); only append to the registry array.
- Every new user-visible string gets a translation key, an English string in \`frontend/src/app/locales/en\`, and an inline \`defaultValue\` fallback.

---

## Troubleshooting

**Module does not appear under Modules & Marketplace.** The backend must have been restarted after dropping the folder. Check the startup log for \`[modules] loaded oe_your_module\`. Missing? Verify \`__init__.py\` exists and \`manifest.py\` defines a \`manifest\` object at module scope.

**404 on your routes.** The loader prefixes with \`/api/v1/<module_name>/\`. So \`router.py\` paths like \`@router.get("/")\` become \`/api/v1/my_module/\`. Keep the trailing slash on the frontend API client; \`redirect_slashes\` is disabled on the backend.

**Alembic autogenerate produces an empty migration.** Alembic only sees models imported at app startup. Add \`from app.modules.my_module import models as _m  # noqa: F401\` to \`_import_models_for_migrations\` in \`backend/app/main.py\`.

**Frontend shows a raw i18n key like \`modules.my_feature.title\`.** You forgot the English string. Add it to \`frontend/src/app/locales/en\` with an inline \`defaultValue\`. The app boots from \`locales/en\` and lazy-loads the other locales on demand.

**403 Missing permission: my_module.create.** You declared a new permission but no role has it. Edit \`backend/app/modules/users/seed_roles.py\` and re-run seed. Admin always bypasses; every other role needs an explicit grant.

**TypeScript error in manifest.ts about routes.** The contract lives in \`frontend/src/modules/_types.ts\`; import \`ModuleManifest\` from there. Never modify \`_types.ts\` or the shape of \`_registry.ts\`; only append your import to the \`MODULE_REGISTRY\` array.

**Nav item not appearing in the sidebar.** Check that \`defaultEnabled\` is true in \`manifest.ts\` (users can still disable it later), and that the nav item's \`group\` matches an existing sidebar group id. \`advancedOnly: true\` hides the item until the user turns on Advanced mode in Settings.

---

## Sharing your module with others

Once your module works locally, package it as a zip so others can install it with one command.

\`\`\`bash
# 1. Build a zip of the module folder
cd backend/app/modules
zip -r ~/my-module-0.1.0.zip my_module

# 2. Share the zip; recipients install with:
openconstructionerp module install ~/my-module-0.1.0.zip

# 3. Distribute the zip yourself (your own site or package index).
#    There is no central module repository to submit to.
\`\`\`

Always bump \`manifest.version\` on every release; the installer uses it to decide when to upgrade an existing install.

---

## Further reading

- [MODULES.md on GitHub](https://github.com/datadrivenconstruction/OpenConstructionERP/blob/main/MODULES.md): single source of truth
- [CONTRIBUTING.md](https://github.com/datadrivenconstruction/OpenConstructionERP/blob/main/CONTRIBUTING.md): style, commits, PR process
`;function $(t){return t.toLowerCase().replace(/`/g,"").replace(/[^a-z0-9]+/g,"-").replace(/(^-|-$)/g,"")}const h=k.split(`
`).map(t=>/^##\s+(.+?)\s*$/.exec(t)).filter(t=>t!==null).map(t=>{const n=(t[1]??"").trim();return{id:$(n),text:n.replace(/`/g,"")}}).filter(t=>t.id.length>0);function V(){const{t}=E(),[n,a]=y.useState("");y.useEffect(()=>{if(!(typeof window>"u"||!window.location.hash))try{const e=document.querySelector(window.location.hash);e&&e.scrollIntoView({behavior:"smooth",block:"start"})}catch{}},[]),y.useEffect(()=>{if(h.length===0)return;const e=h.map(i=>document.getElementById(i.id)).filter(i=>i!==null);if(e.length===0)return;const r=new IntersectionObserver(i=>{for(const p of i)p.isIntersecting&&a(p.target.id)},{rootMargin:"-76px 0px -70% 0px",threshold:0});return e.forEach(i=>r.observe(i)),()=>r.disconnect()},[]);const c=(e,r)=>{const i=document.getElementById(r);i&&(e.preventDefault(),i.scrollIntoView({behavior:"smooth",block:"start"}),a(r),typeof window<"u"&&window.history.replaceState(null,"",`#${r}`))},s=t("modules.dev_guide_on_this_page",{defaultValue:"On this page"});return d.jsxs("div",{className:"space-y-5 animate-fade-in",children:[d.jsx(M,{items:[{label:t("nav.modules","Modules"),to:"/modules"},{label:t("modules.dev_guide","Developer guide")}]}),d.jsx(I,{srTitle:t("modules.dev_guide_title",{defaultValue:"Build your own module"}),subtitle:t("modules.dev_guide_subtitle",{defaultValue:"A practical, 10-minute walkthrough for adding business features to OpenConstructionERP."}),actions:d.jsxs(x,{to:"/modules",className:"inline-flex items-center gap-1 text-xs text-content-tertiary hover:text-oe-blue transition-colors",children:[d.jsx(T,{size:12}),t("modules.back_to_modules",{defaultValue:"Back to Modules & Marketplace"})]})}),d.jsxs("div",{className:"flex flex-col gap-x-10 gap-y-6 xl:flex-row",children:[d.jsx(R,{padding:"none",className:"min-w-0 max-w-[76ch] flex-1 p-6 md:p-8",children:d.jsx(O,{source:k})}),h.length>0&&d.jsx("aside",{className:"hidden shrink-0 xl:block xl:w-64",children:d.jsxs("nav",{"aria-label":s,className:"sticky top-20 max-h-[calc(100vh_-_7rem)] overflow-y-auto overscroll-contain pr-2",children:[d.jsx("p",{className:"mb-3 text-xs font-semibold uppercase tracking-wide text-content-tertiary",children:s}),d.jsx("ul",{className:"space-y-0.5 border-l border-border-light",children:h.map(e=>{const r=n===e.id;return d.jsx("li",{children:d.jsx("a",{href:`#${e.id}`,onClick:i=>c(i,e.id),"aria-current":r?"location":void 0,className:A("-ml-px block border-l-2 py-1 pl-3 text-sm leading-snug transition-colors",r?"border-oe-blue font-medium text-oe-blue":"border-transparent text-content-tertiary hover:border-border hover:text-content-primary"),children:e.text})},e.id)})})]})})]})]})}export{V as ModuleDeveloperGuide,V as default};
