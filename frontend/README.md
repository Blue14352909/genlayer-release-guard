# ReleaseGuard — frontend

**Consensus-backed software release verification.**

A Next.js (App Router, TypeScript, Tailwind CSS) dApp that talks **directly** to the
deployed ReleaseGuard Intelligent Contract on **GenLayer Studionet**. There is no
backend, no mock data, and no server-side signing: reads go straight to the chain and
every write is signed by the user's injected EIP-1193 browser wallet.

---

## What this app is (and is not)

ReleaseGuard is an **evidence-based, fail-closed release attestation tool**. It asks the
contract to evaluate public release evidence against a requested policy and reports the
consensus outcome.

| Verdict        | Meaning                                                    |
| -------------- | ---------------------------------------------------------- |
| `VERIFIED`     | Every requested check explicitly passed.                    |
| `REJECTED`     | At least one requested check failed.                        |
| `INCONCLUSIVE` | Evidence or consensus could not establish a confident result. |

`VERIFIED` does **not** mean the software is objectively safe, audited, or free of
defects — it means the specific requested checks passed on the supplied evidence. If a
requested check is unknown, malformed, or cannot be evaluated, the contract fails closed
to `INSUFFICIENT_EVIDENCE` and the run ends `INCONCLUSIVE`.

> This deployment is a **Studionet demonstration**. It carries no legal, security, or
> fitness-for-purpose guarantee.

---

## Deployed contract

| | |
| --- | --- |
| Network | GenLayer Studionet (`61999`, `https://studio.genlayer.com/api`) |
| Contract | `0xfFa341Ad1AC8aD5DB23405767be481eDDc8f5a46` |
| Repository | https://github.com/Blue14352909/genlayer-release-guard |
| Deployment tx | [`0xf0be0826…cb4a73e`](https://explorer-studio.genlayer.com/tx/0xf0be08268d6d471a2316670a53ff7971db64204e00348a22e9fc77f73cb4a73e) |
| Verified execution tx | [`0xf13317be…d9b6e3f2b`](https://explorer-studio.genlayer.com/tx/0xf13317be4cb28b184e5521eda04f02ca45fcb0612edbf9c1013f954d9b6e3f2b) |
| Explorer | https://explorer-studio.genlayer.com |

Contract methods used by this app:

```
create_verification(project_name, version, evidence_url, policy_text) -> str
run_verification(verification_id) -> str
get_verification(verification_id) -> dict
get_verdict(verification_id) -> str
get_check_results(verification_id) -> list
```

Supported policy names are exactly `source`, `license`, `vulnerability`. The policy text
sent to the contract is the comma-separated selection made on the New Verification page.

A ready-made example that resolves to a real, already-decided on-chain record is
`v-1` (`requests` `2.31.0`, policy `source,license`). Use **Load example** on the
Inspect page.

---

## Requirements

- Node.js 20+ (developed on Node 24) and npm.
- An **EIP-1193 browser wallet** (MetaMask or compatible) — required only for writes.
- **Test GEN** on Studionet to pay for `create_verification` / `run_verification`.
  Writes are real transactions and may incur Studionet fees; reads are free and need no
  wallet at all.

This app never asks for a private key or seed phrase, never creates an auto-funded
account, and never signs on the server. Only the connected wallet can sign.

---

## Local development

```bash
cd frontend
npm install
cp .env.example .env.local   # already contains the deployed address
npm run dev                  # http://localhost:3000
```

Scripts:

```bash
npm run dev     # Next.js dev server
npm run build   # production build (must pass with no errors)
npm run start   # serve the production build
npm run lint    # ESLint (eslint-config-next)
```

### Environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `NEXT_PUBLIC_RELEASE_GUARD_ADDRESS` | no | Deployed ReleaseGuard contract address. Defaults to the Studionet deployment above if unset. |

`NEXT_PUBLIC_*` values are embedded in the browser bundle, so **never** put a private
key, seed phrase, API key, or wallet secret in `.env.local`. That file is git-ignored
(`.env.example` is committed on purpose).

If the variable is missing or malformed the app falls back to the known deployment so it
stays usable instead of breaking.

---

## How the write flow works

1. **Validate locally.** Project name, version, and an HTTPS evidence URL are checked
   before any wallet interaction; at least one policy must be selected.
2. **Require the right wallet and network.** The app checks the injected provider and
   that `eth_chainId` is Studionet (chain id `61999`). It offers a one-click
   *Switch to GenLayer Studionet* (and will add the chain if the wallet does not know it).
   The app enforces this itself because the SDK intentionally skips its network check on
   Studio chains.
3. **Pre-flight.** `simulateWriteContract` dry-runs `create_verification` (`sim_call`) so
   obvious failures surface before the user pays anything. The predicted verification id
   it returns is treated as a **prediction only**.
4. **Estimate and submit.** `writeContract` estimates gas via the SDK's
   `estimateTransactionGas` (falling back to `200_000` gas) and hands the transaction to
   the wallet for signing.
5. **Show the hash and the lifecycle.** The transaction hash, an explorer link, and the
   live decision state (polling `getTransaction` until a decided status) are displayed.
6. **Confirm the id against chain state.** Only after the decision does the app read the
   record back. If the returned id cannot be confirmed from chain state, the app says so
   and asks you to paste the id from the confirmed transaction — it **never invents** a
   verification id.

The Inspect page runs the same lifecycle for `run_verification` when a record is still
`PENDING`, and refreshes the stored data only after the decision is available.

### SDK version note (important)

This app pins **`genlayer-js@1.1.8`** (the current stable `latest`) rather than the
`2.0.0-rc` line, for one measured reason: the release candidate cannot read this
Studionet deployment. During development, the same `readContract` call
(`get_verification("v-1")`) returned `VERIFIED` on `1.1.8` but failed with
`GenLayer RPC error (gen_call): execution failed` on `2.0.0-rc.1`. `1.1.8` is the only
published version whose `gen_call` encoding works against the live contract, so it is
what ships here.

Consequence: the explicit fee-preset API (`estimateTransactionFees` /
`estimateTransactionFeesForWrite`, `fees` on `writeContract`) exists **only** in the RC.
On `1.1.8` the SDK performs fee estimation internally — `estimateTransactionGas` before
submission, with a `200_000` gas fallback — and this app additionally runs a pre-flight
simulation before asking the wallet to sign. When a stable release gains the explicit fee
API *and* can read Studionet, swapping it in is a small, contained change in
`src/lib/genlayer.ts`.

Transactions submitted against a Studio chain come back as an **EVM transaction hash**;
the app links that hash to the explorer rather than pretending it is a GenLayer tx id.

---

## Pages

- `/` — landing page: how it works, supported checks, the fail-closed rule, and public
  evidence links (repository, deployment tx, verified execution tx).
- `/new` — create a verification: validated form, policy checkboxes showing the exact
  `policy_text` sent on-chain, and the full write lifecycle. Includes a *Try the verified
  example* helper.
- `/inspect` — read a stored verification (`get_verification`, `get_verdict`,
  `get_check_results`), per-check status/evidence/reason, and the `run_verification`
  flow when a record is still `PENDING`. Supports deep links: `/inspect?id=v-1`.

Wallet UX lives in the header: connect, shortened address, network status, switch
network, and a local disconnect (the browser wallet owns the real connection). All
contract- and user-provided text is sanitized and rendered as text — never as HTML.

---

## Deploy to Vercel

This app is in a subdirectory, so set the project root accordingly:

1. In Vercel, **Add New → Project** and import
   `https://github.com/Blue14352909/genlayer-release-guard`.
2. Set **Root Directory** to `frontend`. Vercel detects the Next.js framework preset and
   the `npm run build` script automatically.
3. Add the environment variable `NEXT_PUBLIC_RELEASE_GUARD_ADDRESS` =
   `0xfFa341Ad1AC8aD5DB23405767be481eDDc8f5a46` (optional — the code falls back to this
   exact value — but explicit is better for deployments).
4. **Deploy.** No secrets or build-time keys are needed.

The app is fully client-side: pages are statically prerendered and all chain access
happens in the browser against the public Studionet RPC, so no server runtime
configuration is required.

---

## Verification status

- `npm run build` — passes, TypeScript clean.
- `npm run lint` — passes with no errors or warnings.
- `get_verification("v-1")` on the deployed contract — returns `VERIFIED` with
  `source` and `license` both `PASS` (verified live during development).
- `simulateWriteContract` for `create_verification` — returns the next id (verified live).

What still requires a **real browser wallet and a funded Studionet account** to exercise
end to end: signing `create_verification` / `run_verification`, the wallet-side gas
prompt, and the full decision lifecycle for a newly submitted transaction.
