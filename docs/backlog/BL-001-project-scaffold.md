# BL-001 — Project Scaffold

**Size**: S  
**Dependencies**: None

## User Story

As a developer, I want a working Next.js project in the `web/` directory so that I can immediately begin building UI components with TypeScript, Tailwind CSS, and a fast local dev server.

## Acceptance Criteria

- Running `npm run dev` inside `web/` starts a dev server at `http://localhost:3000` with no errors
- Running `npm run build` inside `web/` produces a `web/.next/` output with zero TypeScript errors
- Tailwind CSS utility classes apply correctly (verified by a colored test element on the home page)
- ESLint runs clean with `npm run lint`
- `web/` is self-contained: its own `package.json`, no shared `node_modules` with the repo root
- A `web/.gitignore` excludes `node_modules/`, `.next/`, `out/`
- A `web/README.md` documents how to install dependencies and run the dev server

## Technical Notes

**Scaffold command:**
```bash
npx create-next-app@latest web \
  --typescript \
  --tailwind \
  --app \
  --eslint \
  --no-src-dir \
  --import-alias "@/*"
```

**Resulting structure:**
```
web/
├── app/
│   ├── layout.tsx       ← root layout (shell goes here in BL-004)
│   ├── page.tsx         ← home page (redirect to /pricing)
│   └── globals.css
├── components/          ← create empty dir for BL-005+
├── lib/                 ← create empty dir for BL-003+
├── public/
│   └── data/            ← create empty dir for BL-002
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

**Tailwind config** — ensure content glob covers all components:
```ts
// tailwind.config.ts
content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"]
```

**tsconfig.json** — verify `"strict": true` is set.

**next.config.ts** — no special config needed initially; leave as default.

**Verify scaffold works:**
- Edit `app/page.tsx` to render `<h1 className="text-red-500">Hello</h1>`
- Run `npm run dev` and confirm red heading appears at `localhost:3000`
- Remove test element before committing

## Verification

```bash
cd web
npm install
npm run dev        # should open localhost:3000 with no errors
npm run build      # should exit 0 with no TypeScript errors
npm run lint       # should exit 0
```
