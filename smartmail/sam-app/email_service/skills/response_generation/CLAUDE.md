# response_generation/ — Response Generation Skill

## Key Files

| File | Role |
|---|---|
| `prompt.py` | Main response generation prompt |
| `schema.py` | Output schema |
| `validator.py` | Output validation |
| `runner.py` | Skill runner |
| `errors.py` / `eval.py` | Error types + offline eval |
| `communication_copy.py` | Copy templates |
| `language_render.py` | Language rendering helpers |
| `evaluation_prompt.py` | Quality evaluation prompt |

## Contracts (outside this package)

- `../../response_generation_contract.py` — `ResponseBrief`, `FinalEmailResponse`, reply modes
- `../../response_generation_assembly.py` — assembles `ResponseBrief` from coaching artifacts

## Known Gap

RG1.8 (fallback behavior) is unimplemented — failures fail-closed with logging, no fallback reply sent.

The `ResponseBrief → FinalEmailResponse` contract and reply-mode system are implementation choices, not invariants. Both are fair game to restructure.
