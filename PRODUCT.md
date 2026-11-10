# Product

<!-- impeccable:product-schema 1 -->

Inferred from the written brief (no interactive answer mechanism in this build session); every fact below comes from the project's own README, METHOD.md, SOLUTION.md and results files.

## Platform

web

## Users
Camera-module mechanical engineers and their leads who own tolerance budgets for compact lens modules. They open the page from a short walkthrough video or a link, and read it top to bottom in two or three minutes.

## Product Purpose
Answer one question with a measured answer: which drawing-level tolerances in a compact camera module actually set image-quality yield after autofocus, and how far a standard RSS tolerance estimate is from a full ray-traced Monte Carlo. Then hand over a reallocated budget, a playbook and a CLI tool.

## Positioning
Every number is traced: a published six-element phone lens rebuilt from patent tables, 6,000 simulated modules ray-traced with refocus, a trained surrogate scored against a second-order stack on held-out modules, and a reallocated budget checked by a fresh Monte Carlo.

## Operating Context
Readers know MTF charts, slanted-edge targets, lens cross-sections, GD&T callouts and tolerance tables. The page is recorded as a single top-to-bottom scroll.

## Capabilities and Constraints
Static site, results precomputed as JSON. No company or person names. Modules are a physics simulation, labelled as such. Results must be stated with their intervals and honest limits.

## Evidence on Hand
results/summary.json, results/validation.json, results/budget_reallocated.json, web/public/data/figures.json (lens rays, held-out scatter).

## Product Principles
- Question, measured answer, solution in the first viewport.
- Show the baseline beside the model, including where the baseline ties.
- One visual per step; tables and method behind "Show details".
