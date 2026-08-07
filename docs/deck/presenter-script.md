# Presenter Script — Multi-Tenant NER Platform
### Audience: CxO (CEO / CRO / CTO-level). Three presenters. ~25 minutes + live demo + Q&A.

---

## HOW THIS SCRIPT WORKS

This is written for an executive room, not a technical review. That changes three things versus a normal walkthrough:

1. **Lead with consequence, follow with mechanism.** Never explain a component before you've said why it matters commercially. A CxO who hears "PostgreSQL per-tenant schemas" before "your data is never in the same table as a competitor's" has already stopped listening.
2. **Define nothing pre-emptively.** Definitions are parked in `[PLAIN ENGLISH — ONLY IF ASKED]`. Volunteering them reads as talking down. Wait to be asked, then answer in one sentence and move on.
3. **Never leave a claim unbanked.** Every slide has a `[LAND THIS]` — the single sentence that must survive the meeting. If you get cut short on a slide, say the `[LAND THIS]` and move on.

Each block gives you:

- **[SAY]** — the narration.
- **[LAND THIS]** — the one sentence that must survive.
- **[PLAIN ENGLISH — ONLY IF ASKED]** — definitions, held in reserve.
- **[IF ASKED]** — likely executive questions with a short, confident answer.
- **[DON'T SAY]** — guardrails against overclaiming. Read these twice. A CxO forgives "I'll get you that number"; they don't forgive a number that turns out to be invented.
- **[HANDOFF]** — the exact line that passes the floor to the next presenter.

---

## THE THREE-WAY SPLIT

| | Presenter | Owns | Slides | Time |
|---|---|---|---|---|
| **P1** | The problem & the gap | Why this exists and why nobody sells it | Cold open, 01 Hero, 02 Contents, 03 The Missing Pieces | ~7 min |
| **P2** | The platform & the moat | What we built and why it's defensible | 04 Meet the Platform, 05 Multi-Tenant Context, 06 End-to-End Workflow | ~9 min |
| **P3** | The engine & the proof | How it's built, then show it working | 07 Architecture, 08 Live Demo, 09 Close | ~9 min + demo |

**Q&A quarterback: P3.** When a question comes in after the close, P3 takes it or names who takes it — out loud ("that's P2's area"). Three people all half-answering the same question is the single fastest way to look unprepared in front of an executive.

**One rule between you:** never re-explain what a previous presenter has already covered. If P1 has defined multi-tenancy, P2 uses the word without hesitating. That hesitation is what makes a three-hander feel like three separate meetings.

---

## THE THROUGH-LINE — READ THIS BEFORE ANYTHING ELSE

Our differentiator is **multi-tenancy with real data isolation**. But you must never say the words "our USP is." The room decides what your USP is; your job is to make that conclusion unavoidable.

So it gets seeded three times, by three different people, in three different vocabularies, and it's only *named* once — on P2's slide 05, where the diagram is already saying it for you.

| Where | Who | The seed — phrased as a business fact, not a feature |
|---|---|---|
| Cold open | P1 | "Every client wants their own model. Nobody wants to run a separate stack per client." |
| Slide 03 | P1 | "None of those six tools has any concept of a tenant. So you end up building one stack per customer — and that's how you get silos." |
| Slide 04 | P2 | "One governed workspace per customer." |
| **Slide 05** | **P2** | **The full argument — isolation, the noisy neighbour problem, silos.** |
| Slide 06 | P2 | "The approval gate is also a cost gate — one tenant can't quietly burn the pool." |
| Slide 07 | P3 | "Isolation isn't a policy here, it's four separate enforcement points." |
| Close | P3 | "Shared logic, never shared data." |

**The phrase to repeat — all three of you, verbatim: "isolation without fragmentation."** That's the whole pitch in three words. Isolation = every customer sealed. No fragmentation = one codebase, one deployment, one thing to sell and support. Say it, and let the room work out that this is the hard part.

**Three ideas that must land, without ever being listed as a feature list:**

- **Data isolation** — a customer's documents, model, schema and search index are physically separate from every other customer's. Not filtered. Separate.
- **The noisy neighbour problem** — on most shared platforms, one heavy customer degrades everyone else's experience. Ours is built so one tenant's expensive month is not another tenant's slow afternoon.
- **Silos** — the interesting one, because it cuts both ways, and this is the framing that makes CxOs lean in:
  - *Between* customers: hard silos. That's the sales answer to "is my data safe."
  - *Inside* a customer: HR, Finance and Legal can each hold their own sealed tenant, with their own fields and their own model — so departments stop fighting over one shared schema.
  - *For us*: no silos at all. One codebase, one deployment. Customer number fifty costs us almost nothing more to onboard than customer number five.

That last bullet is the one a CEO or CRO actually cares about, because it is a margin statement dressed as an architecture statement. **Do not say it as a margin statement.** Say the architecture, and let them arrive at the margin themselves. They will, and it will be their idea, which is worth far more than it being yours.

---
---

# PRESENTER 1 — THE PROBLEM & THE GAP

*Your job: make the room feel the problem in 90 seconds, then prove nobody has solved it. You are not selling the product — you are making the product inevitable. Energy high, no notes, no deck for the first 90 seconds.*

---

## COLD OPEN — BEFORE THE DECK IS ON SCREEN (90 seconds)

**[SAY]**

"Before we open anything — one example, because the product only makes sense once you've felt the problem.

Take any document-heavy team. Our own HR team gets a few hundred résumés a week. Somewhere in each one is a name, a last employer, a degree, a set of skills, a notice period. Today a human reads every one of them to pull that out. It's slow, it's inconsistent — two recruiters reading the same résumé will tag different things as 'skills' — and it does not scale when hiring doubles.

Now, general AI tools can pull names and companies out of generic text. What they can't do is know that *your* documents have *your* structure — that 'B.Tech CSE' means something specific to your screening criteria, or that a notice period matters to you and to nobody else. A general model was trained on the internet. It was not trained on your business.

So the only way to get extraction you can actually run a process on is to train a model on your own documents. And until now, that meant assembling five or six separate tools — a labelling tool, a training pipeline, a model registry, a database, a search layer, and a business app on top — and stitching them together, with your own engineers, **for every single client.**

That last part is the part I want you to hold on to. Every client wants their own model. Nobody wants to run a separate stack per client.

That's the problem we set out to solve. Everything in the next twenty minutes is the mechanics."

**[LAND THIS]**
> "Every client wants their own model. Nobody wants to run a separate stack per client."

**[DON'T SAY]**
- Don't name a real customer or a real hiring number unless it's cleared. "A few hundred a week" is safe and vivid; a specific client name is a liability.
- Don't say "ChatGPT can't do this." It can do a version of it. Say it can't do it *repeatably on your formats* — that's the true and stronger claim.

**[HANDOFF — into Slide 01]**
"Here's the one-line version."

---

## SLIDE 01 — HERO

**On screen:** *Multi-tenant NER Platform.* Subtitle about teams defining their own data types, labelling, training, extracting. Three stats: 1 tenant → 1 model · 4 roles → one continuous loop · 0 tools to stitch. InApp logo top-right.

**[SAY]**

"NER is Named Entity Recognition — the technical name for what I just described: a model reading a document and pulling out the specific things the business cares about. A name, a date, an invoice number, a contract clause.

Multi-tenant means one platform, many completely separate customers. One building, many locked units — same infrastructure, no shared doors.

Read the three numbers as one sentence: **every customer gets their own model, four roles carry the entire loop from setup to answer, and there is nothing to stitch together.** That last zero is the commercial one. It's the difference between a product we ship and a project we staff."

**[LAND THIS]**
> "Zero tools to stitch — that's the difference between a product we ship and a project we staff."

**[PLAIN ENGLISH — ONLY IF ASKED]**
- **NER:** finding and labelling specific pieces of information inside unstructured text.
- **Tenant:** one customer organisation on the platform, with its own users, data and model.

**[IF ASKED] "How is this different from just asking ChatGPT to read the document?"**
"A general model guesses, and it guesses differently each time. That's fine for a human reading the output and fine for a one-off. It's not fine for a process you run four hundred times a week and audit later. We train a dedicated model on your documents, so extraction is consistent, versioned, and improves as your team uses it."

**[HANDOFF]**
"Quick map of where we're going."

---

## SLIDE 02 — CONTENTS

**On screen:** 01 The Missing Pieces · 02 Meet the Platform · 03 Multi-Tenant Context · 04 End-to-End Workflow · 05 Architecture.

**[SAY]**

"Five stops. The gap in the market as it stands today. The platform itself. Then the part I'd ask you to pay most attention to — how four different organisations run on one deployment without ever touching each other's data. Then the workflow between the roles, the architecture underneath, and we finish live in the product.

[NAME] takes you through the middle three, [NAME] takes the architecture and the demo."

*(Keep this to fifteen seconds. Nobody has ever been won over by a contents slide — but flagging slide 03 as "the one to watch" primes the room to take the USP seriously when it arrives.)*

**[HANDOFF]**
"Start with the gap — because the product only makes sense once you've seen what's missing."

---

## SLIDE 03 — THE MISSING PIECES

**On screen:** Six segments, each a tooling category with named vendors and where it stops. OCR (Textract · Azure Vision · Tesseract — stops at text) · Annotation (Label Studio · Labelbox · Prodigy — stops at export) · Training (SageMaker · Vertex AI AutoML — stops at API) · Registry (MLflow · W&B — built for ML engineers) · Search (Elasticsearch · Pinecone — doesn't know entities) · Business App (you build this yourself — every time, from scratch). Closing line: *"We're not a better annotation tool or another MLflow. We're the piece nobody sells — the one that connects all six."*

**[SAY]**

"This slide is the entire competitive argument on one screen, so I'll spend a minute on it.

The market is fragmented, not bad. Every one of these six categories has strong, mature players. The problem is where each of them *stops.*

OCR — reading text off a scanned page — stops at text. You get words, with no idea what they mean to your business. Annotation tools stop at export: your team finishes labelling and the tool hands back a file. Training platforms stop at an API endpoint: a model, with no labelling workflow feeding it and no approval gate in front of it. Registries are excellent, and built for ML engineers — no business owner is opening MLflow to check which model is live. Search finds you a document mentioning 'termination clause'; it can't tell you that clause was extracted, structured and tied to a contract field. And the business app — the thing a person actually touches to ask a question — today the honest answer is: you build that yourself. Every time.

Now here's the part that isn't on the slide, and it's the one I'd underline. **Not one of these six has any concept of a tenant.** They were all designed for one organisation, one workspace, one dataset. So the moment you're serving several customers, or several departments who can't share data with each other, the only way through is to stand up a separate copy of the whole stack for each of them. Separate infrastructure, separate deployments, separate upgrade cycles, separate everything. That's how you end up running silos instead of a platform — and every new customer makes it worse rather than better.

So, precisely: we are not trying to out-build Label Studio at labelling, or out-build MLflow at registry. Those are solved. What doesn't exist is the connecting layer — governed, multi-tenant, business-facing. That's the whitespace, and that's what we built."

**[LAND THIS]**
> "None of the six has any concept of a tenant. That's why everyone ends up running one stack per customer — and that's how you get silos instead of a platform."

**[PLAIN ENGLISH — ONLY IF ASKED]**
- **OCR:** turning a scanned image or PDF into machine-readable text.
- **Annotation:** humans marking examples so a model can learn from them.
- **Model registry:** version control for trained models — which version exists, which one is live, how to roll back.
- **Vector search:** finding content by meaning rather than exact keyword match.

**[IF ASKED] "Couldn't a good engineering team just wire these six together?"**
"They can, and many do. But they've now got six vendor relationships, six sets of API changes to track, and they still have to build the connecting layer themselves — the approval workflow, the tenant isolation, the business interface. And they build it again for the next customer, because none of those six will carry the tenancy for them. That connecting layer *is* the product."

**[IF ASKED] "Why hasn't AWS or Google built this connecting layer already?"**
"Their incentive runs the other way. SageMaker, Textract, each of these is a separate product line with its own revenue. Nobody with that P&L structure is motivated to build the thing that makes their six products unnecessary to shop for individually."

**[IF ASKED] "So who is the competitor?"**
"Category by category, everyone on this slide. As a whole, the honest answer is: the customer's own engineering team, and a nine-month internal project. That's who we're usually beating, and it's a much easier fight than beating Label Studio at labelling."

**[DON'T SAY]**
- Don't disparage the named vendors. A CTO in the room may be running three of them, and the argument doesn't need it — "stops at" is a stronger and more respectful frame than "isn't good enough."

**[HANDOFF — to P2]**
"That's the gap. [NAME] will show you what we built to close it."

---
---

# PRESENTER 2 — THE PLATFORM & THE MOAT

*Your job is the heart of the pitch. Slide 05 is the most important slide in the deck — the entire differentiator lives there. Budget your time so you arrive at it unhurried. If you're running late, compress slide 04, never slide 05.*

---

## SLIDE 04 — MEET THE PLATFORM

**On screen:** *"A multi-tenant SaaS platform that goes beyond extracting entities by transforming an organization's documents into intelligent, searchable knowledge through annotation, custom model training, deployment, and AI-powered querying — all within a single governed workspace."* Three animated stages: **Ingest** · **Annotate & Fine-tune** · **Serve**. Below them, the four roles: System Admin (platform owner) · Tenant Admin (workspace owner) · Annotator (labelling) · Business User (day to day).

**[SAY]**

"This is the answer to the gap [NAME] just walked through.

One sentence: a multi-tenant platform that turns an organisation's documents into searchable knowledge — annotation, custom training, deployment and querying — inside **one governed workspace per customer.** Hold on to 'governed workspace per customer,' because it's carrying a lot. It means all six of those categories live under one roof, with one set of permissions, one audit trail, and a hard boundary around each customer.

Three stages carry the loop.

**Ingest.** The customer uploads their documents and defines their own fields. Not our fields — theirs. We assume nothing about what matters to their business.

**Annotate and fine-tune.** Their people mark examples; the platform trains a model on those examples. That progress ring is standing in for something important — nothing goes live until a named person confirms it's ready.

**Serve.** The trained model runs against new documents, and what comes back isn't a wall of text. It's structured, queryable results — which is exactly the search and business-app gap from the previous slide, closed.

And four roles carry that loop end to end. Our **System Admin** provisions tenants, sets quotas, and approves training before any GPU time is spent. The customer's **Tenant Admin** owns their workspace — defines the fields, assigns the work, submits training, promotes the model. **Annotators** work a queue and label. **Business Users** are the day-to-day: upload, extract, query, export.

The distribution of those four is worth noting. One of them is us. Three of them are the customer. Once a tenant is provisioned, they run their own lifecycle — we're not in the loop for their day-to-day. That's what makes this scale as a product rather than as a services engagement."

**[LAND THIS]**
> "One of the four roles is us. Three are the customer. That's what makes this a product rather than a services engagement."

**[PLAIN ENGLISH — ONLY IF ASKED]**
- **Governed workspace:** every action — upload, label, train, promote — happens under defined permissions and is visible and auditable, instead of scattered across disconnected tools.
- **Fine-tuning:** taking a general model and training it further on a customer's own labelled documents so it specialises in their content.
- **Entity types / schema:** the fields a customer wants pulled out — defined by them, not fixed by us.

**[IF ASKED] "How much labelled data does a customer need before this is useful?"**
> ⚠️ **FILL THIS IN BEFORE THE MEETING** — get the real minimum-viable-dataset figure from the ML team, ideally as a range by document complexity. Do not guess in the room. If you genuinely don't have it: "That varies by document type and I'd rather give you the real curve than a number I've rounded — I'll have it to you today."

**[IF ASKED] "What stops a customer doing this in-house with open-source tools?"**
"Nothing stops them trying. But they'd be rebuilding tenant isolation, the approval workflow, model versioning and rollback, and a serving layer that scales — which is where the actual engineering went. That's months of work most teams would rather spend on their own product."

**[HANDOFF]**
"Now, one platform serving many customers raises an obvious question, and it's usually the first one a CIO asks. So let's answer it directly, on the next slide."

---

## SLIDE 05 — MULTI-TENANT CONTEXT ★ THE MOST IMPORTANT SLIDE

**On screen:** C1 system context. Four tenant organisations across the top — InApp HR (résumés) · InApp Finance (invoices) · Gordian Construction (contracts) · Healthcare Provider (clinical records) — each with their own entity types. Below: one platform deployment, one API gateway ("the only door in"), and four sealed tenant scopes, each showing its own database schema, own storage and vectors, own entity types, own fine-tuned model. Then a shared foundation bar: *"Shared logic — never shared data."* Bottom: System Admin, a "NO CROSS-TENANT PATH" callout, and two external systems.

*This slide builds in six steps. Use them. Do not reveal the whole thing and then talk over it — click, say the line, click. The build is doing rhetorical work for you.*

**[SAY — step by step]**

**[Step 1 — the four organisations]**
"Four organisations. An HR team working résumés. A finance team working invoices. A construction firm working contracts. A healthcare provider working clinical records.

Look at what they need extracted. Candidate, employer, skill. Vendor, invoice number, tax ID. Contract, milestone, site. Diagnosis, medication, dosage. There is no universal schema here. Nobody could have designed one model that serves all four — and that's the point. Each of these needs its own model.

And notice two of them are the same company. HR and Finance are separate tenants. That's deliberate — inside a single organisation, HR data and finance data usually *shouldn't* mix, and the departments shouldn't have to agree on a shared schema in order to both use the platform. They each get their own sealed space, and neither is blocked waiting on the other."

**[Step 2 — one platform, one door]**
"All four run on **one deployment.** Not four installations — one. Every request from every one of them enters through a single door, and that door does two things before anything else happens: it establishes who you are, and it establishes which tenant you belong to. From that point on, every query the system makes is scoped to your tenant. There is no unscoped path through this system."

**[Step 3 — the four sealed scopes]**
"Here's what 'sealed' actually means, and I want to be specific, because 'isolated' is a word every vendor uses.

Each tenant gets **its own database schema** — its own tables, not shared tables with a customer column. **Its own object storage and its own vector index.** **Its own entity types** — invisible to everyone else; Finance cannot see that HR has defined a 'notice period' field, and vice versa. And **its own fine-tuned model**, version-pinned per request — so when Finance promotes a new model version, HR's extractions don't change at all. Nothing about their day moves.

The distinction that matters: this isn't row-level filtering, where everyone's data sits in one table and a `WHERE` clause keeps them apart. One missing clause in one query, and you're in an incident. Here, the separation is structural — a query in the wrong tenant's scope doesn't return someone else's rows, it finds nothing at all, because those tables aren't there."

**[Step 4 — the shared foundation]**
"Now the other half, and this is the half that makes it a business.

Underneath all four: one base model, one training pipeline, one serving pool that routes per tenant. So while the *data* is four separate worlds, the *engineering* is one. One codebase to maintain, one deployment to upgrade, one set of improvements that lands for every customer at once.

That line on the bar is the whole design philosophy: **shared logic, never shared data.** Or, as we tend to put it — isolation without fragmentation.

And this is where the practical failure mode of shared platforms usually shows up. Most multi-customer systems have a noisy neighbour problem: one customer runs something enormous and everyone else's afternoon gets slower. We designed around it deliberately. The heavy work — training a model, extracting across a large batch — never runs on the live request path. It's queued and worked in the background, so a large tenant's expensive job and a small tenant's routine lookup aren't competing for the same moment. And any training run has to clear a named approval before it consumes anything, which we'll see on the next slide.

The honest framing: it's structural separation plus an explicit spend gate, not a hardware guarantee. If a customer needs contractual, hardware-level separation, we can talk about a dedicated deployment — the architecture supports it. But the default is designed so they shouldn't need to ask."

**[Step 5 — governance]**
"Bottom left: the System Admin — us. Provisions tenants, sets quotas, approves training. Cross-tenant by design, and the only role that is.

And the callout next to it is the one to read carefully. **No cross-tenant path.** Not 'we're careful about it' — there isn't one. Enforced at four independent points: the gateway, the connection pool, the data access layer, and the storage prefix. Four separate places, any one of which would stop a leak on its own. That's what makes it something you can put in front of a security review rather than something you have to explain your way through."

**[Step 6 — external systems]**
"Two external dependencies, and I'll be precise because this is the question a CIO always asks next. We pull a base model from Hugging Face — once, at setup. No tenant data goes with it. And we call Azure OpenAI for chat and embeddings, always within the tenant's scope.

Everything else — the documents, the labels, the trained models, the extractions — stays inside the deployment."

**[LAND THIS]**
> "Shared logic, never shared data. Four sealed customers, one codebase — isolation without fragmentation."

**[PLAIN ENGLISH — ONLY IF ASKED]**
- **Per-tenant schema:** each customer's tables live in their own named section of the database, rather than sharing tables with a customer-ID column.
- **Version-pinned:** each request is served by a specific, named model version, so promoting a new model never silently changes anyone else's results.
- **Noisy neighbour:** when one customer's heavy workload degrades performance for everyone else on shared infrastructure.

**[IF ASKED] "Are these four real customers?"**
> ⚠️ **These four are illustrative, not live customers.** Say so plainly and immediately: "These are representative scenarios — chosen because they show four genuinely different schemas on one deployment. Happy to walk you through where we actually are on pipeline separately." Vagueness here does more damage than the answer itself ever would. A CxO will forgive an early-stage pipeline; they will not forgive discovering later that a logo on a slide wasn't real.

**[IF ASKED] "What does it cost us to add a tenant?"**
"A schema, a storage prefix and an index — provisioning, not deployment. No new infrastructure and no new code path. The marginal cost of customer fifty is close to the marginal cost of customer five."
*(This is the answer a CFO or CEO is actually listening for. Don't rush it, and don't editorialise after it — let it sit.)*

**[IF ASKED] "What if a customer demands their own dedicated instance?"**
"Supported — it's the same deployment, just dedicated. Worth noting it's a pricing conversation rather than an engineering one, which is exactly where you want that conversation to sit."

**[IF ASKED] "Has this been through a security audit? Is it SOC 2 / GDPR / HIPAA ready?"**
> ⚠️ **AGREE THIS ANSWER BEFORE THE MEETING.** Know the current status and say it exactly — including "not yet, and here's the plan," which is a perfectly respectable answer at this stage. What you can say confidently in any case: *"The architecture was built for that review rather than retrofitted to it — per-tenant schemas, no cross-tenant path, and enforcement at four independent layers is what those audits actually look for."* Never claim a certification you don't hold. That's the one mistake in this room you cannot walk back.

**[DON'T SAY]**
- Don't say "impossible" or "cannot ever happen." Say "no cross-tenant path exists, enforced at four independent points." Equally strong, and it survives cross-examination by a technical CxO.
- Don't say the noisy neighbour problem is "solved" — say it's designed around, structurally, and name the mechanism.
- Don't present the four tenants as customers. See above.

**[HANDOFF]**
"That's how four organisations stay separate. Now let's follow one of them through — who does what, and where the control points are."

---

## SLIDE 06 — END-TO-END WORKFLOW

**On screen:** Swimlane, four lanes (System Admin, Tenant Admin, Annotator, Business User), eleven numbered steps. Solid arrows are human handoffs; dashed red is automated. Labelled: *"Training executes"* and *"Latest promoted model."*

**[SAY]**

"Same story as a process. Four lanes, one per role, eleven steps, left to right.

We create the tenant. The Tenant Admin uploads documents for fine-tuning and assigns them to an annotator with the entity fields to look for. The annotator labels. The Tenant Admin submits a training job. **We approve it** — step six, and it's the one worth pausing on. Training executes automatically after that, which is the dashed red line; dashed always means the machine, not a person. Once it's done, the Tenant Admin promotes the model — that's the moment it becomes live. And from there it's the business user's world: upload documents, extraction runs against the latest promoted model, query the results.

Two things I'd point out.

First, every place where judgement should exist has a named human on it. Approving spend. Confirming labels. Promoting a model to live. Nothing consequential happens without someone accountable for it — which is exactly what an auditor asks for, and exactly what's missing when a team has stitched six tools together.

Second, step six is quietly doing double duty. It's a quality gate — no half-labelled dataset goes to training. And it's a cost gate — training is the expensive operation on this platform, and it cannot start until we've said yes. That's how a shared platform stays predictable: no tenant can independently decide to consume the pool."

**[LAND THIS]**
> "Every step with judgement in it has a named human on it — and the approval gate is both the quality gate and the spend gate."

**[PLAIN ENGLISH — ONLY IF ASKED]**
- **Swimlane:** each row is one role; boxes are actions; arrows are handoffs.
- **Promote:** formally marking a specific trained version as the live one.
- **Dashed line (this deck's convention):** an automated background process, not a human action.

**[IF ASKED] "What if a promoted model performs badly in production?"**
"Roll back to the previous version — that's what the registry is for. Versions aren't overwritten, they're kept, and promotion is a pointer. [NAME] will show you where that lives in the architecture."

**[IF ASKED] "Is the approval step a bottleneck? Won't customers hate waiting on us?"**
"It's one click on a request that arrives with the dataset already summarised, and it only fires at training time — not on any day-to-day operation. Nothing a business user does waits on us. And when we want to remove it for a mature account, it's a policy setting rather than a rebuild."

**[IF ASKED] "Who's the buyer, and who's the daily user?"**
> ⚠️ **Have your actual GTM answer ready.** This is the CRO's question and it comes up almost every time. Know whether the Tenant Admin is the economic buyer or whether someone above them signs while Business Users drive usage and renewal — because that determines the whole sales motion, and "we're still figuring that out" is a bad look in front of a revenue leader.

**[HANDOFF — to P3]**
"That's the human layer. [NAME] will take you under it — and then show you the whole thing running."

---
---

# PRESENTER 3 — THE ENGINE & THE PROOF

*Your job: prove the architecture is real without turning the room into an engineering review, then show it working. The failure mode here is depth. A CxO doesn't need to understand the architecture — they need to believe you do. Every box gets one sentence with a business consequence attached. If you find yourself explaining what Redis is, you've lost them.*

*The four pipelines are click-to-expand. **Expand at most two** — the ML pipeline and the chatbot. Leave the others compressed; the fact that they expand tells the room there's depth there without you having to spend the minutes.*

---

## SLIDE 07 — ARCHITECTURE

**On screen:** Frontend → API Gateway (single entry point, FastAPI · JWT · tenant context) → four pipelines (Document, ML, Extraction & Analytics, Analytics & Chatbot) → Data Layer (per-tenant: Object Storage, PostgreSQL, Vector Database) + Async Tasks (Celery + Redis, off the request path).

**[SAY — top to bottom, with the build steps]**

"I'll keep this to the shape rather than the detail — happy to go as deep as you want afterwards.

**Top — the frontend.** One web application. Every role logs into the same place and sees a different product.

**The gateway.** One door in. It authenticates the user and resolves which tenant they belong to, and it stamps that onto every request before anything downstream sees it. This is the enforcement point [NAME] described — the isolation isn't a policy document, it starts here, at the only entrance.

**Four pipelines underneath**, each independent, each scaling on its own.

**Document** — turning uploads into readable text, and the annotation workspace where labelling happens.

**ML** — this is the interesting one, so I'll expand it. *[click]* Training runs the fine-tune. The registry versions every run — and that's where promote and roll back live, which is the answer to '[NAME], what if a model misbehaves.' Nothing is overwritten; promotion just moves a pointer. And model serving runs the live model. Worth noting: the trained model is converted into an optimised format for production, which is why serving is fast and cheap enough to keep per-tenant models running side by side. That conversion step is a big part of why one-model-per-customer is economically sane rather than a nice idea.

**Extraction** — runs the model against live documents and applies a confidence threshold, so what surfaces is what the model is actually sure about, not low-confidence guesses. That threshold is the difference between a demo and something a business will run a process on.

**Analytics and chatbot** — *[click]* the 'talk to your documents' layer. A question comes in, and an orchestrator decides how to answer it: precise, structured questions go through a language model that writes the database query — 'how many candidates have five-plus years and a CS degree.' Fuzzy, meaning-based questions go to vector search — 'find résumés similar to our best hires.' Either way, a plain-English answer comes back. The business user never sees a query, and never files a ticket asking someone to run one.

**The data layer, and read the label on it — per tenant.** Storage, database, vector index. Three stores, replicated per tenant, which is the physical version of that sealed box from the previous slide. This is where the isolation stops being architecture and becomes a fact about where bytes live.

**Bottom left, async tasks.** Training and large batch extractions take minutes, not milliseconds. They're queued and run in the background, off the request path. Two consequences, both commercial: nobody's browser sits frozen, and — back to the noisy neighbour point — one tenant's heavy job runs in a queue rather than in everyone else's way.

That's the whole system. The thing I'd take from it: isolation isn't asserted in one place here. It's the gateway, the connection scope, the data layer and the storage prefix — four independent enforcement points, on a single shared codebase."

**[LAND THIS]**
> "Isolation isn't one control here — it's four independent enforcement points on one shared codebase."

**[PLAIN ENGLISH — ONLY IF ASKED]** *(hold these back — offering them unprompted is what makes an architecture slide feel like a lecture)*
- **API gateway:** the single entry point every request passes through, where identity and tenant are established.
- **JWT:** a tamper-proof token proving who the user is, checked on every request.
- **Microservices:** independently deployable components, each doing one job, so they scale and update separately.
- **ONNX:** a portable, optimised format for running a trained model fast in production.
- **Confidence filter:** only surfacing results the model is sufficiently sure about.
- **Celery / Redis:** the background queue that runs slow jobs off the live request path.
- **Vector database:** stores meaning-based representations of documents, for similarity search.

**[IF ASKED] "If one tenant runs a huge training job, do the others slow down?"**
"Two things stop that. Training never touches the live request path — it's queued and run in the background, so day-to-day extraction and querying are unaffected. And no training run starts at all until a System Admin approves it, so there's a deliberate gate in front of the expensive operation. Under sustained load we scale workers; if an account needs a contractual guarantee rather than a design principle, that's a dedicated deployment, and the architecture supports it without a fork."
*(This is the noisy-neighbour question arriving in its natural habitat. Answer it fully and calmly — it's a buying signal.)*

**[IF ASKED] "Why two chatbot paths instead of one?"**
"They answer different question shapes. Structured counting questions need an exact database query. 'Find me things like this' needs similarity. Forcing one technique to do both is how you get confidently wrong answers, which is worse than no answer. The orchestrator picks per question."

**[IF ASKED] "What's your dependency risk on Azure OpenAI / Hugging Face?"**
"Hugging Face is a one-time pull of a base model at setup — not a runtime dependency. Azure OpenAI is used for chat and embeddings, and it's a swappable component; the orchestrator interface doesn't care which model sits behind it. No tenant data leaves the deployment for training."

**[IF ASKED] "How long does a training run take end to end?"**
> ⚠️ **GET THE REAL NUMBER BEFORE THE MEETING** — a range is fine, a shrug is not. "It depends" without a figure sounds like you haven't run one.

**[DON'T SAY]**
- Don't walk the four pipelines at equal depth. Two expanded, two named. Depth signals nervousness in this room.
- Don't name a framework unless it earns its place. "Optimised for production" beats "ONNX Runtime" unless a technical CxO asks.
- Don't claim hard per-tenant resource guarantees. Say queued, gated, and scalable — which is true — and offer dedicated deployment as the path to a contractual guarantee.

**[HANDOFF]**
"Rather than keep describing it — let's open it."

---

## SLIDE 08 — LIVE DEMO

**[SAY]**
"I'll run the same path we just walked. A tenant being set up, fields defined, a look at annotation, and then the part worth waiting for — an already-trained model answering a plain-English question about a document set it's never been asked about before."

### Demo discipline — read before the meeting

- **Rehearse the exact click path twice on the machine you'll present from.** Not a similar path. The same one.
- **Pick your model and dataset deliberately.** Demo a version and a tenant you've verified end to end this week. If a particular model version has known accuracy problems, do not put it on screen — the room will remember exactly one number from the demo and it must not be a bad one.
- **Have a fallback.** Screenshots or a short recording, ready to open in one click. If the environment misbehaves, switch inside ten seconds — "let me show you the recorded version while that comes back" is a non-event; two minutes of live troubleshooting is the only thing anyone remembers.
- **One isolation moment, no narration needed.** If you can show two tenants side by side — different fields, different models, same platform — do it and say nothing except *"same deployment."* That single moment does more for the multi-tenancy story than the entire slide 05 build. Let the screen carry it.
- **Don't demo everything.** Four minutes, one clean thread, stop while they still want more. An over-long demo turns a pitch into a training session.

---

## SLIDE 09 — CLOSE

**On screen:** *Thank you!* — Ingest · Annotate · Fine-tune · Serve.

**[SAY]**

"To close where [NAME] opened.

Every organisation with documents wants a model that understands *their* documents. Until now that meant one stack per customer, six vendors, and an engineering project each time.

What you've seen is that same capability as a single platform — four customers, four sets of fields, four models, one deployment. Sealed from each other, sharing every improvement we make. Shared logic, never shared data.

That's the whole thing. Happy to go deeper anywhere — the architecture, the numbers, or where we take it next."

**[LAND THIS]**
> "Four customers, four models, one deployment. Shared logic, never shared data."

---

## Q&A — QUESTIONS THAT AREN'T TIED TO A SLIDE

*P3 quarterbacks. Route out loud and by name. If nobody has the answer, one person says "we'll come back to you with that today" and it moves on — three people improvising in sequence is worse than one honest deferral.*

**"What's the cost structure — per tenant, per training run, per query?"**
> ⚠️ Fill in before the meeting. Almost certain to come up. Do not construct a pricing model live in front of a CRO.

**"What's the roadmap?"**
> ⚠️ Agree the top three items between you beforehand, and agree who answers. Three different roadmaps in one room is the worst possible answer to this question.

**"How defensible is this? What stops a competitor copying it?"**
"The multi-tenancy is the moat, and it's the part that can't be retrofitted. Anyone can wire six tools together for one customer. Rebuilding a single-tenant system into a properly isolated multi-tenant one is close to a rewrite — which is why most products that start single-tenant never make the jump."

**"What's the team size behind this?"**
> ⚠️ Straight factual answer, agreed beforehand. This is usually a question about burn rate and bus factor, not curiosity — answer the real question.

**"Who's the ideal first customer?"**
"Any organisation with high document volume, its own document formats, and a reason not to send them to a general AI service — regulated industries, or anyone with several departments who can't share data with each other. That second group is interesting, because they're a multi-tenant sale inside a single logo."

**"Where does this fail? What can't it do today?"**
"Answer this one honestly and specifically — a prepared weakness builds more credibility than any strength you've claimed, and a CxO who asks this is testing whether you know your own product. Have one real limitation ready and say it plainly."

---

## DELIVERY NOTES — ALL THREE

- **Cold open and demo carry the room; the slides in between carry the argument.** P1's ninety seconds and P3's four minutes are the parts they'll retell. Rehearse those two hardest.
- **Say the plain-English version before the term, never after.** "Turning a scan into readable text — that's OCR." Nobody feels talked down to that way.
- **No number you can't source.** "I'll have that to you today" costs you nothing. An invented figure is the only thing in this meeting you can't take back.
- **Repeat "isolation without fragmentation" at least three times, across at least two presenters.** Repetition across speakers is what turns a phrase into a takeaway.
- **Watch the room split.** The CRO drives pricing, competition and the sales motion. The CEO drives defensibility, roadmap and team. Route toward whoever asked.
- **Land the handoffs by name, and don't recap.** A three-hander is judged on the seams. Three people who sound like one argument beats three people who each did a good section.
