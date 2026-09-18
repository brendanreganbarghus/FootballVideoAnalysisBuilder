# Project documentation map

This is the maintained entry point for developers and coding agents taking
over the Football Video Analysis Builder. It identifies every committed
Markdown document, what it controls, and when to read it. The map prevents
agent-specific instructions from becoming duplicate and conflicting copies of
the project architecture.

## Authority and maintenance model

Use the smallest appropriate layer:

1. **Canonical rules and architecture** define football law, analytics
   contracts, evidence boundaries, workflow separation, review, and
   publication.
2. **Implementation and tests** enforce those contracts and reveal the exact
   current behavior.
3. **Operational guides** explain setup, commands, artifacts, and validation.
4. **Agent entry points** state non-negotiable boundaries and point to this
   map; they do not replace canonical documents.
5. **Demo and presentation documents** explain approved claims and
   reproduction. They are not inference specifications.

When documentation conflicts, do not silently choose the convenient version.
Stop, compare it with the canonical architecture and code/tests, and correct
the stale document. A current user instruction may select or pause a
workstream, but it must not bypass data-leakage protections, evidence
requirements, protected regressions, or publication gates.

## Required takeover reading

Every new developer or coding agent should:

1. Read the root [`README.md`](../README.md) for project scope, setup,
   limitations, and data locations.
2. Read [`AGENTS.md`](../AGENTS.md) for current workstream boundaries and
   cross-agent rules.
3. Read
   [`RULES_ENGINE_ARCHITECTURE.md`](RULES_ENGINE_ARCHITECTURE.md) before any
   football-event, evidence, inference, review, or publication work.
4. Read [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) for ownership, code paths,
   storage tiers, and dependency-aware validation.
5. Read [`MANUAL_PIPELINE_COMMANDS.md`](MANUAL_PIPELINE_COMMANDS.md) before
   running Innovation or Live processing.
6. Inspect the relevant implementation, current git changes, and focused tests.
   Repository documentation does not contain private conversation history or
   guarantee that a generated local artifact is current.

## Canonical engineering documents

| Document | Role | Read when |
| --- | --- | --- |
| [`README.md`](../README.md) | Repository overview, installation, limitations, data setup, benchmark entry points, and knowledge-pack links | First contact with the project |
| [`PROJECT_DOCUMENTATION.md`](PROJECT_DOCUMENTATION.md) | Maintained inventory, authority model, takeover checklist, and task-based reading paths | Choosing which documentation controls a task |
| [`RULES_ENGINE_ARCHITECTURE.md`](RULES_ENGINE_ARCHITECTURE.md) | Canonical law profile, analytics definitions, raw-video/evaluation boundary, match-state contracts, C#/E# independence, Innovation/Live isolation, guarded acceptance, regression, and publication | Any football-event or rules-engine decision |
| [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) | Target architecture, package ownership, module map, shared/local storage, development setup, rerun matrix, and safe tuning | Implementing or validating code |
| [`MANUAL_PIPELINE_COMMANDS.md`](MANUAL_PIPELINE_COMMANDS.md) | Exact Innovation and Live commands, artifact namespaces, provenance, Canvas identities, cache/cold-run distinction, and troubleshooting | Running or rebuilding a pipeline |
| [`GRASSROOTS_PILOT.md`](GRASSROOTS_PILOT.md) | Pilot stack, licensing, camera/team/pitch calibration, outputs, and pilot acceptance gates | Pilot deployment or camera configuration |
| [`benchmarks\alfheim\README.md`](../benchmarks/alfheim/README.md) | Alfheim non-commercial restrictions, raw-video benchmark preparation, evaluation-label separation, and Match Lab behavior | Using Alfheim footage or benchmark artifacts |

## Agent entry points

| Document | Consumer | Purpose |
| --- | --- | --- |
| [`AGENTS.md`](../AGENTS.md) | Any coding agent | Shared concise role, current boundary, evidence rules, and canonical links |
| [`CLAUDE.md`](../CLAUDE.md) | Claude | Claude startup instructions and mandatory reading order |
| [`.github\copilot-instructions.md`](../.github/copilot-instructions.md) | GitHub Copilot | Detailed persistent football-review and Canvas adjudication instructions |

Keep hard boundaries concise in agent entry points. Put durable technical
detail in the canonical engineering documents and link to it. When a current
boundary changes, update all three entry points in the same change.

## Demo and communication documents

| Document | Role | Authority boundary |
| --- | --- | --- |
| [`demo\README.md`](../demo/README.md) | Build and present the team demo | Presentation workflow only; not an inference contract |
| [`demo\az-demo-video\README.md`](../demo/az-demo-video/README.md) | Reproduce technical and executive videos, captions, and local media inputs | Build and claim guidance; generated video is not evidence for engine behavior |
| [`demo\az-demo-video\STORYBOARD.md`](../demo/az-demo-video/STORYBOARD.md) | Technical demo scene timing and visual plan | Presentation plan only |
| [`demo\az-demo-video\EXECUTIVE_STORYBOARD.md`](../demo/az-demo-video/EXECUTIVE_STORYBOARD.md) | Executive narrative and approved architecture claim boundaries | Presentation claims only; proposed architecture is not current behavior |
| [`demo\az-demo-video\SOCCERTRACK_CREDITS.md`](../demo/az-demo-video/SOCCERTRACK_CREDITS.md) | SoccerTrack footage attribution | Attribution only |

## Task-based reading paths

| Task | Required documents |
| --- | --- |
| Review a pass, turnover, foul, restart, shot, or goal | `AGENTS.md`, rules architecture, relevant implementation/tests |
| Review or accept C#/E# events | Rules architecture Sections 7–10, applicable Canvas instructions, protected review regressions |
| Work on Innovation Day | `AGENTS.md`, rules architecture Section 7.1, manual pipeline guide's workflow table and Innovation commands |
| Resume Live ball tracking | Obtain Brendan's explicit authorization first, then update the three agent entry points and read the Live sections of the architecture/manual guide |
| Run a benchmark | Rules architecture hard input boundary, manual pipeline guide, dataset-specific benchmark README |
| Change possession or event inference | Rules architecture, developer guide module map/rerun matrix, focused and protected tests |
| Configure a pilot or camera | Grassroots pilot profile, developer guide, dataset/camera provenance |
| Build presentation material | Relevant demo README/storyboard plus the canonical architecture for factual claim verification |

## Skills policy

Do not convert the full documentation set into skills. A skill is appropriate
only for a bounded repeatable procedure, such as adjudicating one event,
accepting an independently verified proposal, publishing a reviewed segment,
or running a protected regression package. Skills must link to the canonical
documents and must not copy or weaken their rules.

Critical protections belong in code and tests as well as documentation. Agent
instructions and skills improve discovery but are not enforcement mechanisms.
