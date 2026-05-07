---
version: 1.0.0
last_updated: 2026-05-07
---

# Context Is Not Conversation

**Version:** 1.0.0
**Status:** Active
**Last updated:** 2026-05-07

---

## Overview

This document states the architectural thesis behind Lumina's interaction model.

> **Conversation is what was said. Context is what the system knows.**

Conversation logs are input/output records. They are useful for audit and replay, but they are not sufficient operational context for governed AI execution.

---

## A. The Problem: Half the Equation

Most conversational AI systems treat transcript history as their primary state store. That leaves the model to infer missing operational facts on every turn: task shape, state, rules, tool scope, and constraints.

That inference burden is the root of several recurring failures:

| Failure mode | Why it appears |
|---|---|
| Hallucination | Missing context is filled with plausible text |
| Drift | No explicit task lifecycle to measure progress against |
| Injection susceptibility | Authority is inferred from text rather than enforced by structure |
| Weak auditability | Logs show output text, not the governing state behind decisions |

---

## B. Context vs. Conversation

Conversation and context are different layers.

| Layer | What it contains |
|---|---|
| **Conversation** | Turn-by-turn text: what user/model said |
| **Operational context** | Task definition, model-pack rules, actor state, turn data, module scope, and active invariants |

Operational context must be maintained as first-class structured state. If context is reconstructed from transcript text, the model is forced to guess the system state it should have been given directly.

---

## C. Every Interaction Is a Task

Every interaction has a task shape, even when the interface is conversational.

A one-shot weather query, a multi-turn planning request, and a guided algebra tutoring flow are different task types with different completion criteria, invariants, and allowed actions.

For governed behavior, each interaction should carry at least:

- task type and lifecycle state
- scoped tool/action surface
- current module/model-pack scope
- deterministic turn data extracted from current input
- invariant checks and escalation conditions

Without this structure, turns are only dialogue. With it, turns are measurable progress or measurable drift.

---

## D. The Missing Kernel

A language model is a probabilistic reasoning layer, not a runtime kernel.

A governed runtime needs deterministic components around it that maintain task state, apply invariants, enforce scope, and persist causal records. In Lumina, these concerns are handled by the surrounding architecture (inspection middleware, prompt packet assembly, policy gates, and ledger writes), not delegated to free-form generation.

> Logs tell you what happened. Ledger-style turn records explain why, under what context, and under which active constraints.

---

## E. The Turn Interpreter as Command Interpreter

A turn interpreter is analogous to a command interpreter.

It receives raw input, classifies it, and converts it into structured turn data that downstream deterministic and probabilistic layers can act on safely.

| Traditional computing | Lumina interaction runtime |
|---|---|
| Command interpreter | Turn interpreter / pre-interpreter |
| Grammar + constraints | Model-pack/domain invariants |
| Process state | Actor behavioral state |
| Execution scope | Module-scoped tools and references |

This conversion step is load-bearing: raw text alone is not a reliable execution contract.

---

## F. Behavioral State Is Not Conversational History

Behavioral state is compressed, structured, persistent state about what happened over time. It is not raw transcript retention.

Examples of behavioral state include:

- task progress and completion trajectory
- invariant outcomes over recent turns
- actor baseline shifts and trend direction
- module-specific interaction history in summarized form

This state is more actionable and more privacy-respecting than replaying full text history, because it preserves governing signals without storing every utterance as operational memory.

---

## G. Scoped Context: Give the Right Thing, Not Everything

Larger context windows make brute-force stuffing easier, but that is not governance.

Scoped retrieval and module/model-pack isolation are correctness and safety architecture:

- load the context required for this task, in this module, for this actor
- exclude irrelevant cross-domain material by structure, not by polite instruction
- pass deterministic facts and constrained references rather than unbounded transcript context

The model should receive the sensory/operational data it needs for the current task. It should not be asked to infer missing context from transcript text.

---

## H. Semantic Compilation

Semantic compilation applies familiar computing ideas one layer up:

- loops and conditionals over interaction state
- function-like tool calls under explicit contracts
- invariants and pre/post conditions for each turn
- scoped execution boundaries and state transitions

The objective is the same as in classic systems engineering: deterministic control around probabilistic reasoning.

This is also where capability honesty is enforced. A system must know what it is and what it is not. For example, it must not claim to have contacted emergency services unless an authenticated integration executed and an audit trail proves that action occurred.

---

## SEE ALSO

- [`ai-governance-principles(7)`](ai-governance-principles.md) — governing principles derived from this thesis
- [`prompt-packet-assembly(7)`](prompt-packet-assembly.md) — how structured context is assembled before model inference
- [`compressed-state-pattern(7)`](compressed-state-pattern.md) — deterministic compression patterns for behavioral state
- [`domain-pack-anatomy(7)`](domain-pack-anatomy.md) — model-pack structure and scoped boundaries
- [`edge-vectorization(7)`](edge-vectorization.md) — per-domain retrieval isolation
- [`command-execution-pipeline(7)`](command-execution-pipeline.md) — governed action routing and authority gates
- [`state-change-commit-policy(7)`](state-change-commit-policy.md) — ledger requirement for state mutation
