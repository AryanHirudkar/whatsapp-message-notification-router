# WhatsApp Message Notification Router

## Overview

This project is an AI-powered **WhatsApp Message Notification Router** developed for the HackerRank Challenge. The system analyzes incoming WhatsApp messages and intelligently determines whether they should:

* **notify** – immediately interrupt the user.
* **digest** – be grouped into a later notification summary.
* **mute** – be suppressed because they are low-value, repetitive, suspicious, or unsafe.

The solution is designed to make **personalized notification decisions** by combining user history, business relationships, group context, historical interactions, deterministic safety rules, and multimodal AI reasoning.

---

# Features

* Personalized notification routing
* Deterministic safety rule engine
* LLM-based reasoning for complex cases
* Image understanding using a vision model
* Voice note transcription using Whisper
* Historical message retrieval
* User, group, and business context awareness
* Evidence-based decision making
* Confidence scoring
* Structured output compliant with the HackerRank specification

---

# System Architecture

```
Incoming Messages
        │
        ▼
Dataset Loader
        │
        ▼
Message Indexer
        │
        ▼
Context Builder
        │
        ▼
Deterministic Rule Engine
        │
 ┌──────┴──────┐
 │             │
Matched      Not Matched
 │             │
 ▼             ▼
Prediction   Media Processing
                  │
                  ▼
           Image / Voice Analysis
                  │
                  ▼
             Prompt Builder
                  │
                  ▼
              Groq LLM
                  │
                  ▼
             Final Prediction
                  │
                  ▼
            Output Writer
                  │
                  ▼
        dataset/output.csv
```

---

# Supported Message Types

The router predicts one of the following categories:

* personal
* urgent
* event
* payment
* business_update
* promotion
* greeting
* forward
* spam
* scam
* unknown

---

# Routing Actions

Each incoming message is classified into one of three actions:

| Action | Description                                        |
| ------ | -------------------------------------------------- |
| notify | Important enough to interrupt the user immediately |
| digest | Useful but can wait for a notification summary     |
| mute   | Low-value, repetitive, suspicious, spam, or scam   |

---

# Context Used for Decision Making

The system incorporates information from multiple datasets to personalize routing decisions:

* User profile and notification behavior
* Group metadata and membership
* Business account information
* User-business interaction history
* Historical messages
* Historical message events
* Daily notification summaries
* Image metadata
* Voice note metadata

---

# Multimodal Processing

## Text Messages

Processed directly through the rule engine and LLM.

## Image Messages

Images are analyzed using a vision language model to understand posters, invitations, notices, screenshots, advertisements, scams, and other visual content.

## Voice Notes

Voice notes are transcribed using Whisper before being incorporated into the routing prompt.

---

# Safety Rules

Before invoking the language model, every incoming message is evaluated using deterministic rules.

Examples include:

* Phishing detection
* Prompt injection detection
* Fake OTP requests
* Credential theft attempts
* Suspicious links
* High-forward spam
* Chain messages
* Scam indicators

Messages matched by these rules bypass the LLM and receive immediate predictions.

---

# AI Models

## Language Model

* `llama-3.3-70b-versatile`

Used for contextual reasoning and routing decisions when deterministic rules do not apply.

### Vision Model

* `meta-llama/llama-4-scout-17b-16e-instruct`

Used for image understanding.

### Speech Model

* `whisper-large-v3`

Used for voice note transcription.

---

# Project Structure

```
code/
    data/
    evaluation/
    media/
    output/
    reasoning/
    rules/
    utils/

dataset/
    media/
        audio/
        images/

docs/

tests/
```

---

# Running the Project

Install the required dependencies.

```
pip install -r requirements.txt
```

Configure the required environment variables (for example, API credentials) before running the application.

Execute:

```
python -m code.main
```

The generated predictions will be written to:

```
dataset/output.csv
```

---

# Output Format

The generated `output.csv` contains the following columns:

| Column               | Description                                   |
| -------------------- | --------------------------------------------- |
| message_id           | Incoming message identifier                   |
| action               | notify / digest / mute                        |
| message_type         | Predicted message category                    |
| reason               | Short explanation for the decision            |
| confidence           | Confidence score between 0 and 1              |
| evidence_message_ids | Historical messages supporting the prediction |

---

# Design Principles

The solution follows a layered architecture that separates:

* data loading
* indexing
* context construction
* deterministic reasoning
* multimodal processing
* language model inference
* output generation

This modular design improves maintainability, extensibility, and testing.

---

# Submission Contents

This submission includes:

* Complete runnable source code
* Configuration files
* Project documentation
* Generated `output.csv`

The implementation follows the HackerRank challenge requirements for personalized, multimodal WhatsApp notification routing.
