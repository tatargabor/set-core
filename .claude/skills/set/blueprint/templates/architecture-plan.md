# Architecture plan — <solution name>

Status: **draft for review**, <YYYY-MM-DD>. Built on <internal decisions> and
<research document>. Requirements come from <requirement list / previous offer / meeting notes>.

**Legend.** ⚠ marks an untested assumption; each one names the test (T1…) that settles it,
and that test must pass before the price is fixed.

## 1. The design in five lines

1. <where the core runs, and why>
2. <the client's own interface>
3. <what other people touch, and where>
4. <how the parts connect, and what is deliberately avoided>
5. <what stays in existing tools>

## 2. Where things run

```mermaid
flowchart LR
  %% devices, cloud services, SaaS, people; label each link with its protocol
```

| Place | What runs there | Holds data? |
|---|---|---|

## 3. How the parts talk

| From → To | Protocol | Auth / key | Key stored in | Revocable by |
|---|---|---|---|---|

**Account ownership.** <every account in the client's name; provider as member; exit path>

## 4. Data: stores and ownership

<which store holds what; one writer per table; minimisation; retention parameter; search approach>

## 5. Requirement → component mapping

| Requirement | Component(s) | Notes / ⚠ |
|---|---|---|

## 6. Failure modes and monitoring

- <dependency down / token dead / host silent / retries and idempotency / backup and recovery time>

## 7. Security and data protection

| Sub-processor | Role | Region | Basis |
|---|---|---|---|

<corrections to earlier promises the research disproved>

## 8. Effort estimate (hours)

| # | Component | Low | High |
|---|---|---|---|
| | **Total** | | |

**Against the price band** (<band>, day rate <band>, <h>/day): <does low fit? does high fit?>

<If it does not fit: options with their effect on hours — the choice is the requester's.>

## 9. Monthly running costs

<gross or net, and why; currency rate assumption>

| Item | Paid by | Monthly | Notes |
|---|---|---|---|
| **Real monthly total** | | | |

**One-off extras:** <list>

## 10. Tests that gate the price

| Test | Gates | Pass criterion |
|---|---|---|

**Fallbacks:** <for each test: what replaces it if it fails, and the hours it costs>
