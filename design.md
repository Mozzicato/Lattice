# Lattice — MVP Design Document (Learning-First)

## 1. Overview

Lattice is an AI-powered learning tool designed to help students deeply understand complex research papers, lecture notes, and homework.

The MVP focuses on **how humans actually learn hard material**, not on simulations or visualizations.

Lattice acts like a **patient personal tutor** that:

* explains step by step,
* asks the right questions at the right time,
* and helps users form correct mental models.

---

## 2. Core Product Goal

Enable users to **truly understand complex academic material**, not just read or summarize it.

Success means the user can:

* explain the idea in their own words,
* identify assumptions,
* and feel confident moving forward.

---

## 3. The Top 3 Core Features (MVP)

### 3.1 Socratic Tutor Mode (Primary Feature)

Instead of only explaining content, Lattice **guides understanding through questions**.

**What it does:**

* After each explanation, the system asks targeted questions.
* Questions probe *why* and *how*, not memorization.
* User answers (text or voice) are analyzed to detect misconceptions.
* The next explanation adapts based on the user’s response.

**Why this matters:**

* Learning is active, not passive.
* Mimics how great teachers teach.
* Forces the user to build correct mental models.

---

### 3.2 “I’m Lost” Button (Adaptive Explanation)

A visible, judgment-free button:

> **“I’m lost — explain this differently.”**

**What it does:**

* Automatically switches explanation style.
* Steps back one abstraction level.
* Uses simpler language, intuition, and analogies.
* Removes formalism unless explicitly requested.

**Why this matters:**

* Learners often don’t know *what* they don’t understand.
* Reduces frustration and cognitive overload.
* Creates emotional safety and trust.

---

### 3.3 Mental Model Builder

Lattice explains **structure before math**.

**What it does:**

* Breaks equations and concepts into functional roles:

  * “this term pushes”
  * “this term resists”
  * “this term accumulates over time”
* Explains relationships using conceptual language.
* Shows how pieces interact before formal derivations.

**Why this matters:**

* Experts think in mental models, not symbols.
* Prevents rote memorization.
* Makes future learning faster and easier.

---

### 3.2 “I’m Lost” Button (Adaptive Explanation)

A visible, judgment-free button:

> **“I’m lost — explain this differently.”**

**What it does:**

* Automatically switches explanation style.
* Steps back one abstraction level.
* Uses simpler language, intuition, and analogies.
* Removes formalism unless explicitly requested.

**Why this matters:**

* Learners often don’t know *what* they don’t understand.
* Reduces frustration and cognitive overload.
* Creates emotional safety and trust.

---

### 3.3 Mental Model Builder

Lattice explains **structure before math**.

**What it does:**

* Breaks equations and concepts into functional roles:

  * “this term pushes”
  * “this term resists”
  * “this term accumulates over time”
* Explains relationships using conceptual language.
* Shows how pieces interact before formal derivations.

**Why this matters:**

* Experts think in mental models, not symbols.
* Prevents rote memorization.
* Makes future learning faster and easier.

---

## 4. Input Types (MVP)

* Research papers (PDF)
* Homework problems (PDF or text)
* Handwritten or messy notes (images or scanned PDFs)

---

## 5. Understanding Pipeline (Simplified)

1. **Page Intake**

   * Accept PDF or image input page-by-page.

2. **OCR & Content Recovery**

   * Extract text and mathematical formulas.
   * Preserve page order and structure.

3. **Key Concept Detection**

   * Identify important equations, definitions, and statements.

4. **Understanding Engine**

   * Generate step-by-step explanations.
   * Build mental model representations.
   * Engage Socratic Tutor Mode (text or voice).

5. **Adaptive Learning Loop**

   * Ask questions → evaluate response → adapt explanation.
   * User can respond by typing or speaking.
   * User can trigger “I’m lost” at any time.

---

## 6. Beautification (Supporting Feature)

**Purpose:** Turn messy notes into clean, accurate study material.

**Process:**

* Process content page-by-page (no skipping).
* OCR text and formulas.
* Rewrite explanations clearly.
* Correct grammar, notation, and formatting.
* Reconstruct formulas into clean LaTeX.
* Optionally accept **spoken notes** and transcribe + beautify them.

**Guarantees:**

* Original meaning preserved.
* Page order preserved.
* Low-confidence regions flagged for review.

---

## 7. User Experience Summary

The user experience should feel like:

* talking to a calm tutor,
* working in a clean notebook,
* and being guided without pressure.

The system never rushes, overwhelms, or judges.

---

## 8. Tech Stack (MVP)

* **Backend:** Python + FastAPI
* **OCR:** Text OCR + math OCR (LaTeX reconstruction)
* **Voice:**

  * Speech-to-text for user input
  * Text-to-speech for tutor explanations
  * Push-to-talk interface (no always-on mic)
* **Reasoning & Tutoring:** LLM with structured prompting + response evaluation
* **Verification:** SymPy for basic math consistency checks
* **Frontend:** Simple React app with page viewer, tutor panel, and voice controls

---

## 9. MVP Non-Goals (Explicitly Excluded)

* No simulations or visualizations
* No cross-paper reasoning
* No collaboration features
* No advanced solvers

These are intentionally excluded to protect learning quality.

---

## 10. Product Philosophy (Important)

> **Understanding comes before tools.**

If a user finishes a session feeling calmer, clearer, and more confident — Lattice succeeded.

---
