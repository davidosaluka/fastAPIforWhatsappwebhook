# InTime WhatsApp Webhook & Dispatch Engine 📦🛵💨

Welcome to the **InTime Delivery Platform** backend codebase! This repository contains a production-ready, asynchronous **FastAPI** application designed to serve as a **Meta WhatsApp Cloud API Webhook**. 

The system powers **InTime**, a logistics service in Nigeria connecting package senders with verified motorcycle dispatch riders. It features automated dispatch routing, interactive fare negotiation, real-time status updates via Meta Flows/Buttons, an AI-powered conversational assistant ("Femi"), and automated state-aware background job scheduling.

---

## 📋 Table of Contents
1. [Architecture Overview](#-architecture-overview)
2. [Key Features](#-key-features)
3. [System Sequence & Data Flow](#-system-sequence--data-flow)
4. [Project Structure](#-project-structure)
5. [Database Models & Schema](#-database-models--schema)
6. [Core Workflow & State Machine](#-core-workflow--state-machine)
7. [AI Routing & Femi Conversational Agent](#-ai-routing--femi-conversational-agent)
8. [Background Scheduler & Timers](#-background-scheduler--timers)
9. [Phone Number Normalization System](#-phone-number-normalization-system)
10. [Environment Variables](#-environment-variables)
11. [Setup & Running Locally](#-setup--running-locally)
12. [Deployment](#-deployment)

---

## 🏗️ Architecture Overview

The system is built on a modern, fully asynchronous Python stack:

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Async handlers, Lifespan context manager, OpenAPI specs).
- **ORM & Database**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (`AsyncSession`, `AsyncEngine`) with [PostgreSQL](https://www.postgresql.org/) (`asyncpg` for production/Supabase) and [SQLite](https://www.sqlite.org/) (`aiosqlite` for local development).
- **Database Migrations**: Automatic DDL migrations during startup lifespan + optional [Alembic](https://alembic.sqlalchemy.org/).
- **Task Scheduling**: [APScheduler](https://apscheduler.readthedocs.io/) (`AsyncIOScheduler`) for daily cron check-ins.
- **AI & Natural Language**: [Groq API](https://groq.com/) (`AsyncGroq`) using Llama 3.3 / Llama 3.1 models for semantic intent classification and conversational support.
- **Communication Infrastructure**: Meta WhatsApp Cloud API (Graph API v18.0+) via [`httpx`](https://www.python-httpx.org/).

---

## ✨ Key Features

1. **Meta Webhook Verification & Processing**: Handles GET verification requests and incoming POST webhook events with automated message deduplication (`wamid`).
2. **Interactive Meta Flows & Custom Buttons**: Uses Meta Flows for user registration, order detail entry, fare counter-offers, and fare escalation.
3. **Multi-Rider Broadcast Dispatch**: Broadcasts order requests to all active/available riders within Meta's 24-hour customer service window.
4. **Dynamic Fare Negotiation**: Senders and riders can negotiate prices back and forth seamlessly via interactive WhatsApp forms.
5. **Priority & Medical Deliveries**: Specialized urgency routing for medications and urgent packages (`is_drug`, `is_urgent`, `is_priority`).
6. **5-Digit Verification Code System**: Automated security handshake code dispatched to Sender, Recipient, and Rider prior to package drop-off.
7. **Automated Background Timers**: State-aware background monitoring (`asyncio.create_task`) for order follow-ups, image upload reminders, session timeouts, and arrival checks.
8. **"Femi" AI Assistant**: Multi-turn conversational chatbot powered by Groq LLM that handles general chatter, answers logistics questions, and guides customers to place orders.
9. **Daily Rider Availability Reset**: Automated cron job at 8:00 AM daily resetting riders to `offline` and sending WhatsApp check-in templates.
10. **Account & Data Deletion**: Registered users can delete their user profile & data via template button ("Delete my Account") or natural text intent ("delete my account"). Features an interactive confirmation prompt ("Are you sure...") to prevent accidental deletions.

---

## 🔄 System Sequence & Data Flow

```mermaid
sequenceDiagram
    autonumber
    actor Customer
    participant WhatsApp as Meta WhatsApp Cloud API
    participant FastAPI as FastAPI Webhook Server
    participant DB as Database (PostgreSQL/SQLite)
    participant Groq as Groq AI Engine
    actor Rider

    Customer->>WhatsApp: Sends "Send an Order" or text message
    WhatsApp->>FastAPI: POST /webhook (JSON payload)
    FastAPI->>DB: Log apiRequest & check wamid deduplication
    
    alt Freeform Text Message or Intent
        FastAPI->>Groq: Intent Classification (JSON Mode)
        Groq-->>FastAPI: Intent: "CREATE_ORDER" / "DELETE_ACCOUNT" / "GENERAL_CHAT"
    end

    alt Delete Account Triggered (Button or Intent)
        FastAPI->>WhatsApp: Send Interactive Deletion Confirmation ("Are you sure...")
        alt User Clicks "Yes, Delete"
            Customer->>WhatsApp: Button Reply: CONFIRM_DELETE_ACCOUNT
            WhatsApp->>FastAPI: POST /webhook
            FastAPI->>DB: DELETE FROM users WHERE phone IN (...)
            FastAPI->>FastAPI: Clear user chat memory (_chat_memory)
            FastAPI->>WhatsApp: Send Deletion Confirmation Message
        else User Clicks "Cancel"
            Customer->>WhatsApp: Button Reply: CANCEL_DELETE_ACCOUNT
            FastAPI->>WhatsApp: Send Cancellation Notification
        end
    else Registration Needed
        FastAPI->>WhatsApp: Send Registration Template/Flow
        Customer->>WhatsApp: Submits Name & Details
    else Already Registered
        FastAPI->>WhatsApp: Send Order Details Flow
        Customer->>WhatsApp: Submits Pickup, Dropoff & Fare
        FastAPI->>DB: Save Order (Status: 'confirmed')
        FastAPI->>WhatsApp: Request Package Photo
        Customer->>WhatsApp: Uploads Package Image
        FastAPI->>DB: Update order with package_image_id
        
        Note over FastAPI, Rider: Dispatch Engine Broadcast
        FastAPI->>DB: Query active 'available' riders
        FastAPI->>WhatsApp: Send Dispatch Flow & Image to Riders
        Rider->>WhatsApp: Clicks "Accept" or "Negotiate"
        
        alt Rider Accepts
            FastAPI->>DB: Update order status -> 'rider_accepted'
            FastAPI->>WhatsApp: Notify Customer & Recipient with Rider Details
        else Rider Negotiates
            FastAPI->>WhatsApp: Send Counter-Offer Flow to Customer
        end
    end
```

---

## 📁 Project Structure

```
fastAPIforWhatsappwebhook/
├── alembic/                 # Alembic DB migration environment
├── routers/
│   ├── __init__.py
│   └── createAPIrequest.py  # Primary Webhook Router (POST & GET /webhook)
├── database.py              # Async SQLAlchemy Engine & Session Configuration
├── main.py                  # FastAPI Application Instance & Lifespan Migrations
├── models.py                # SQLAlchemy DB Models (User, Orders, Riders, etc.)
├── replyhandler.py          # Business Logic Engine, Meta API Helpers, AI Agent
├── scheduler.py             # APScheduler Background Cron Jobs (Daily 8 AM Check-in)
├── schemas.py               # Pydantic Schemas for Request/Response Validation
├── .env                     # Environment Variables (Secrets & Configuration)
├── .gitignore               # Git Ignore rules
├── alembic.ini              # Alembic Configuration File
├── Procfile                 # Deployment Command for Heroku/Render
├── requirements.txt         # Python Package Dependencies
└── runtime.txt              # Specified Python Runtime Version
```

### Key Module Descriptions

- `main.py`: Initializes the FastAPI app, manages startup/shutdown lifespan events, performs database schema auto-migrations (renaming columns, adding missing fields dynamically), and starts the background scheduler.
- `routers/createAPIrequest.py`: Handles Meta webhook verification (`GET`) and main event processing (`POST`). Parses incoming message types (`button`, `interactive`, `text`, `image`, `nfm_reply`) and routes them to business logic.
- `replyhandler.py`: The core engine of the application (~1,400 lines). Contains Meta Graph API call wrappers, phone number normalizers, dispatch broadcast logic, order state updates, multi-step background timers, and the Groq LLM integration ("Femi" chatbot).
- `database.py`: Supports PostgreSQL with connection pooling / PgBouncer settings, automatically falling back to an asynchronous SQLite database (`intime.db`) if `DATABASE_URL` is omitted.
- `models.py`: Defines the SQLAlchemy declarative ORM models and order number generators.
- `scheduler.py`: Configures APScheduler with Africa/Lagos timezone to trigger daily rider check-ins at 8:00 AM.

---

## 🗄️ Database Models & Schema

### 1. `User` (`users`)
Stores registered customer information.
| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | Integer (PK) | Auto-increment primary key |
| `name` | String | Customer full name |
| `wa_id` | String (Unique) | WhatsApp ID / Phone number |
| `display_phone_number` | String | Formatted display phone number |
| `phone_number_id` | String | Meta WhatsApp Phone Number ID |

### 2. `Orders` (`orders`)
Central table storing package delivery transactions.
| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | Integer (PK) | Auto-increment primary key |
| `order_number` | String (16, Unique) | Generated alphanumeric identifier (e.g. `ABC1234-XYZ5678`) |
| `sender_wa_number` | String | Customer's WhatsApp phone number |
| `rider_wa_number` | String (Nullable) | Assigned rider's WhatsApp phone number |
| `recipient_phone_number` | String | Package recipient's phone number |
| `package_description` | String | Summary of items being delivered |
| `customer_initial_offered_price` | String | Price offered by sender |
| `final_price_agreed_by_cust_and_rider` | String | Final agreed delivery price |
| `status` | String | Lifecycle state: `confirmed`, `rider_accepted`, `cancelled`, `expired`, `completed` |
| `pickup_location_name` | String | Text address for pickup |
| `dropoff_location_name` | String | Text address for drop-off |
| `pickup_lat` / `pickup_lng` | Float | Geographic coordinates for pickup |
| `dropoff_lat` / `dropoff_lng` | Float | Geographic coordinates for drop-off |
| `package_image_id` | String | Meta Media ID of uploaded package photo |
| `delivery_progression_status` | String | Detailed progress: `package_picked_up`, `package_delivered` |
| `is_drug` / `is_urgent` / `is_priority` | Boolean | Flags for medication/priority handling |
| `sla_expires_by` | DateTime | Service level agreement expiration (default 30 mins) |
| `created_at` | DateTime | Order creation timestamp (UTC) |

### 3. `Riders` (`riders`)
Registered motorcycle dispatch riders.
| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | Integer (PK) | Auto-increment primary key |
| `first_name` / `last_name` | String | Rider full name |
| `rider_wa_number` | String | Primary WhatsApp number |
| `rider_phonenumber_2` | String | Secondary contact number |
| `kyc_status` | String | Verification status (`verified`, `pending`) |
| `availability_status` | String | Current dispatch status: `available`, `offline` |

### 4. `RiderOffer` (`rider_offers`)
Audit log for tracking individual dispatch requests sent to riders.
| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | Integer (PK) | Auto-increment primary key |
| `order_number` | String (Index) | Associated order number |
| `rider_wa_number` | String | Target rider |
| `status` | String | Delivery/Read status: `sent`, `delivered`, `read`, `viewed`, `accepted`, `declined` |

### 5. `apiRequest` (`apiRequests`)
Webhook payload audit log used for deduplication.
| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | Integer (PK) | Primary key |
| `method` | String | HTTP Method (`POST`) |
| `content` | Text | Full JSON string of webhook payload |
| `response` | Text | Webhook processing result |
| `wamid` | Text (Unique) | Meta WhatsApp Message ID (prevents double processing) |
| `status_code` | Integer | HTTP Status |

---

## 🚦 Core Workflow & State Machine

```
┌───────────────┐
│ User Message  │
└───────┬───────┘
        │
        ├──► Taps "Delete my Account" or types "delete account"
        │    │
        │    ▼
        │    Prompt Confirmation ("Are you sure...")
        │    │
        │    ├──► Taps "Yes, Delete" ──► Delete Profile & Chat Memory ──► Account Deleted 🗑️
        │    └──► Taps "Cancel" ───────► Action Cancelled ✅
        │
        └──► Taps "Send an Order" or places order
             │
             ▼
        [Registered?] ──NO──► Send Registration Flow ──► User Registered
             │
            YES
             ▼
   Send Order Details Flow ──► User Fills Form
                         │
                         ▼
                Order Status = "confirmed"
                         │
                         ▼
             Request Package Photo ──► User Uploads Image
                         │
                         ▼
             Broadcast to Active Riders ──► [Rider Action]
                                                │
                          ┌─────────────────────┴─────────────────────┐
                          ▼                                           ▼
                   Rider Accepts                              Rider Negotiates
                          │                                           │
                          ▼                                           ▼
             Order Status = "rider_accepted"                 Customer Prompted with Counter-Offer
                          │                                           │
                          ▼                                 ┌─────────┴─────────┐
             Rider En-Route to Pickup                       ▼                   ▼
                          │                            Accept Offer      Increase Fare
                          ▼                                 │                   │
               Rider Taps "At Pickup"                       └─────────┬─────────┘
                          │                                           │
                          ▼                                           ▼
             Trigger 10-Min Proximity Check                   Re-Broadcast to Riders
                          │
                          ▼
            Send 5-Digit Code to All Parties
                          │
                          ▼
              Rider Taps "At Dropoff"
                          │
                          ▼
             Delivery Completed! 🏁
```

---

## 🤖 AI Routing & Femi Conversational Agent

The system uses **Groq API** (`AsyncGroq`) with fallback across multiple models (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `mixtral-8x7b-32768`, `llama3-70b-8192`):

1. **Intent Classification Engine (`classify_message_intent`)**:
   - Evaluates incoming freeform text using LLM JSON Mode.
   - Categorizes intent into: `CREATE_ORDER`, `CANCEL_ORDER`, `DELETE_ACCOUNT`, `TRACK_ORDER`, `MODIFY_ORDER`, `SUPPORT`, or `GENERAL_CHAT`.
   - Directly routes transactional and account management requests to the corresponding WhatsApp handlers.

2. **Femi AI Assistant (`handle_text_message`)**:
   - Persona: *"Femi, the friendly, energetic AI assistant for InTime 🛵💨"*.
   - Features: Multi-turn in-memory chat history (`_chat_memory`, capped at 10 turns per user), dynamic greeting generation, Nigerian logistics knowledge base, and auto-conversion of standard Markdown (`**bold**`) to WhatsApp single-asterisk formatting (`*bold*`).
   - Behavior: Always answers queries politely while encouraging users to type `Send an Order` to initiate transactions.

---

## ⏱️ Background Scheduler & Timers

### 1. APScheduler Cron Jobs (`scheduler.py`)
- **Daily Rider Check-in**: Runs every day at **8:00 AM Lagos Time**.
- Resets all riders' `availability_status` to `"offline"`.
- Sends the `rider_checkin` WhatsApp template asking riders to press "I'm Available" to re-enroll in daily dispatch.

### 2. Async State-Aware Timers (`replyhandler.py`)
Using non-blocking `asyncio.create_task()`, the application monitors user and order progression:
- **`schedule_registration_reminder`**: Reminds un-registered users 5 minutes after initial interaction.
- **`schedule_user_session_timeout`**: Sends a reminder 5 minutes after order creation if no package photo is uploaded; automatically expires (`status="expired"`) the order after 15 minutes of inactivity.
- **`schedule_order_followups`**: 1 minute after order creation, sends a live read-count status update to the sender; at 3 minutes, prompts the sender with a Meta Flow to increase their fare if no rider has accepted.
- **`schedule_customer_offer_timeout`**: Reminds customer 4 minutes after a rider makes a counter-offer.
- **`_delayed_pickup_arrival_notifications`**: 5 minutes after pickup arrival: checks rider ETA. 10 minutes after pickup: generates a **random 5-digit verification code**, dispatches it to Sender, Recipient, and Rider, and sends the drop-off confirmation Meta Flow to the rider.

---

## 🇳🇬 Phone Number Normalization System

To prevent duplicate user records and handle varied Nigerian dialing formats across local and international standards, `replyhandler.py` provides two essential helpers:

- **`normalize_phone_number(phone: str) -> str`**:
  Converts inputs like `08151033428`, `070...`, `+2348151033428` into the canonical WhatsApp format: `2348151033428`.

- **`get_phone_variants(phone: str) -> list[str]`**:
  Generates all matching variations (`2348151033428`, `08151033428`, `+2348151033428`, `8151033428`) for database queries, ensuring SQL `IN (...)` queries match regardless of how the number was originally stored.

---

## 🔑 Environment Variables

Create a `.env` file in the root directory with the following keys:

```env
# Database Connection String (PostgreSQL or leave blank for SQLite fallback)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/intimedb

# Meta WhatsApp Webhook Verification Token
VERIFY_TOKEN=your_custom_webhook_verification_token

# Meta Access Token (Bearer Token for Graph API)
AUTHORIZATION=EAAG...your_meta_system_user_token

# Meta Graph API Base Endpoint URL
GRAPH_URL=https://graph.facebook.com/v18.0/YOUR_PHONE_NUMBER_ID/messages

# Groq API Key (for LLM intent classification & Femi AI assistant)
GROQ_API_KEY=gsk_your_groq_api_key
```

---

## 🚀 Setup & Running Locally

### 1. Prerequisites
- Python 3.10+
- Virtual environment tool (`venv` or `conda`)
- PostgreSQL (optional; SQLite fallback works out of the box)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/davidosaluka/fastAPIforWhatsappwebhook.git
cd fastAPIforWhatsappwebhook

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Setup
Create your `.env` file based on the environment variable section above.

### 4. Run the Server
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
The FastAPI application will start, auto-apply database migrations, initialize `intime.db` (if using SQLite), and start the background scheduler.

### 5. Expose Webhook for Local Development
Use ngrok to expose your local FastAPI server to Meta:
```bash
ngrok http 8000
```
Configure your Webhook URL in Meta App Dashboard to: `https://<your-ngrok-subdomain>.ngrok-free.app/webhook`

---

## ☁️ Deployment

The codebase includes a `Procfile` configured for Heroku, Render, or Railway:

```procfile
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

Ensure all environment variables (`DATABASE_URL`, `VERIFY_TOKEN`, `AUTHORIZATION`, `GRAPH_URL`, `GROQ_API_KEY`) are properly configured in your platform dashboard.
