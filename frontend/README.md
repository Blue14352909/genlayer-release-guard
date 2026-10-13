# ReleaseGuard Console

**A public, read-only workspace for inspecting software-release verification
results produced by the deployed GenLayer ReleaseGuard contract.**

ReleaseGuard Console is a product layer on top of the accepted ReleaseGuard
intelligent contract. It displays and inspects results; it does not replace,
mock, or reimplement the contract.

- **Live site:** https://genlayer-release-guard.vercel.app/
- **Repository:** https://github.com/Blue14352909/genlayer-release-guard
- **Contract:** `0xfFa341Ad1AC8aD5DB23405767be481eDDc8f5a46` on GenLayer Studionet
- **Network:** GenLayer Studionet (`61999`, `https://studio.genlayer.com/api`)

---

## What it is — and what it is not

ReleaseGuard evaluates a software release against source, license, and
vulnerability policies. GenLayer consensus produces one terminal verdict:

| Verdict        | Exact meaning                                                             |
| -------------- | ------------------------------------------------------------------------ |
| `VERIFIED`     | Every requested check explicitly passed on the supplied evidence.         |
| `REJECTED`     | At least one requested check failed.                                       |
| `INCONCLUSIVE` | Evidence or consensus was insufficient to decide — it fails closed.        |

`INCONCLUSIVE` is **not** a soft pass: a release that could not be evaluated did
not pass, and never resolves to `VERIFIED` on that basis. `VERIFIED` is a policy
result on the supplied evidence — not a security audit or a guarantee.

The Console:

- performs **reads only** — `get_verification`, `get_verdict`, `get_check_results`;
- never connects a wallet, requests a signature, or submits a transaction;
- collects no user data, has no login, and persists nothing about your input;
- shows no mock dashboards, fake activity, placeholder metrics, or invented
  on-chain data. The only pre-seeded record is the real `v-1` example, always
  labelled **Verified example**.

---

## Pages

| Route           | Purpose                                                                                  |
| --------------- | ---------------------------------------------------------------------------------------- |
| `/`             | Home: hero, verdict legend, the verified `requests 2.31.0` example, policies, evidence.   |
| `/inspect`      | **Verify a result** — read a stored verification by id (`/inspect?id=v-1` deep-links).    |
| `/guide`        | **New verification** — guidance only: the exact GenLayer Studio sequence and field rules. |
| `/architecture` | The frontend ↔ contract ↔ consensus trust boundary.                                       |

The result page is the visual centre of the product. It shows project, version,
evidence URL, parsed policy, overall verdict, request status, reason code, failed
checks, and each individual check's status, evidence, and reason. Verdict colours
(VERIFIED green, REJECTED red, INCONCLUSIVE amber, PENDING/RUNNING blue-grey) are
always paired with a text label — colour is never the only signal.

---

## The verified example

`v-1` is a real, already-decided record on the deployed contract.

| Field        | Value                                        |
| ------------ | -------------------------------------------- |
| Project      | `requests`                                   |
| Version      | `2.31.0`                                     |
| Evidence URL | https://pypi.org/project/requests/2.31.0/    |
| Policy       | `source,license`                             |
| Verdict      | `VERIFIED` (source PASS, license PASS)       |

A PyPI release page is appropriate for `source,license`. Request `vulnerability`
only with an advisory page that contains version-specific vulnerability data.

---

## Contract interface used here

```
create_verification(project_name, version, evidence_url, policy_text) -> str
run_verification(verification_id) -> str
get_verification(verification_id) -> dict
get_verdict(verification_id) -> str
get_check_results(verification_id) -> list
```

Creating and running a verification are on-chain writes and are **not** performed
by this app. Run them in GenLayer Studio, then inspect the result here.

---

## Local development

Requirements: Node.js 20+ and npm.

```bash
cd frontend
npm install
cp .env.example .env.local   # already contains the deployed address
npm run dev                  # http://localhost:3000
```

Scripts:

```bash
npm run dev        # Next.js dev server
npm run build      # production build
npm run start      # serve the production build
npm run lint       # ESLint (eslint-config-next)
npm run typecheck  # tsc --noEmit
npm test           # vitest (unit + component tests)
```

### Environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `NEXT_PUBLIC_RELEASE_GUARD_ADDRESS` | no | Deployed contract address. Falls back to the Studionet deployment above if unset or malformed. |

`NEXT_PUBLIC_*` values are embedded in the browser bundle — never put a secret in
`.env.local`. That file is git-ignored; `.env.example` is committed on purpose.

---

## How reads work (and the SDK version note)

Reads go straight from the browser to the public Studionet RPC via
`genlayer-js`. The app pins **`genlayer-js@1.1.8`** (the stable `latest`) for one
measured reason: it is the only published version whose `gen_call` encoding reads
this deployment. During development the same `readContract` call
(`get_verification("v-1")`) returned `VERIFIED` on `1.1.8` but failed with
`GenLayer RPC error (gen_call): execution failed` on `2.0.0-rc.1`.

Because writes are out of scope for the Console, none of the wallet, fee, or
transaction lifecycle code is needed or shipped.

---

## Deploy to Vercel

The app lives in a subdirectory, so set the project root accordingly:

1. In Vercel, **Add New → Project** and import
   `https://github.com/Blue14352909/genlayer-release-guard`.
2. Set **Root Directory** to `frontend`. Vercel detects the Next.js preset and
   the `npm run build` script automatically.
3. Optionally add `NEXT_PUBLIC_RELEASE_GUARD_ADDRESS` =
   `0xfFa341Ad1AC8aD5DB23405767be481eDDc8f5a46` (the code falls back to this
   exact value).
4. **Deploy.** No secrets or build-time keys are required.

Pages are statically prerendered; all chain access happens in the browser against
the public Studionet RPC, so no server runtime configuration is needed.

---

## Verification status

- `npm run lint` — passes with no errors or warnings.
- `npm run typecheck` — passes.
- `npm test` — 41 unit/component tests pass (7 files).
- `npm run build` — passes; `/`, `/guide`, `/architecture` and `/inspect`
  prerender as static routes.
- `get_verification("v-1")` on the deployed contract — returns `VERIFIED` with
  `source` and `license` both `PASS` (verified live during development).

Reads depend on the public `studio.genlayer.com` RPC and CORS availability. If
that endpoint is unreachable, the Console surfaces an explicit error state rather
than showing stale or invented data.
