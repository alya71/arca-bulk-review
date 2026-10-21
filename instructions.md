# MTS Take Home: Bulk Review

## **Context**

A regulatory affairs team at a mid-size pharma company sits on 500k+ documents. Prior submissions and eCTD modules, protocols and amendments, clinical study reports, health authority correspondence, CMC and stability data, SOPs, deviations.

Real asks from this team:

- Pull the 40 CMC sections across our portfolio and, for each: which excipient grade was used, what justification was given, which guidance was cited, and does it contradict the current spec?
- Take 120 health-authority letters and, for each: what commitment did we make, what was the due date, has it been met, who owns it?
- Take our 15 stability protocols and answer the same 6 questions of each: storage condition, timepoints, acceptance criteria, deviations, bracketing justification, post-approval commitment.

## Project

- Design a product that can handle this. Build the frontend and backend and prepare a demo to share.
- Make sure this can handle scale (100k+ concurrent runs), and be ready to discuss tradeoffs.
- Support citations for each claim in the bulk review process
- Full freedom to decide your stack framework, DB, queue/durable execution, models, structured output strategy, UI

Time budget: ~2 hours, then a 45m live walkthrough. AI coding is very encouraged. You won’t build a fully coherent app in this time, but we care more about the decision making process and having a defensible spine + product thinking more so than we do extreme polish. Especially on the infrastructure piece, feel free to just have the scaffolding set up and explain your choices instead of actually testing out massive runs.

## **Deliverables**

- Working code we can run — a real bulk review executing end to end, with evidence we can check.
- Be prepared to talk through your decisions live. An AI generated one-page summary would be great to come with: the shape you chose and what you rejected, the tradeoffs you made, and what you’d do next with a week