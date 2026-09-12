# InTime WhatsApp Webhook Service - Technical Documentation & Developer Guide

**Project Name**: InTime WhatsApp Logistics Engine (`fastAPIforWhatsappwebhook`)  
**Version**: 1.1.0  
**Last Updated**: September 2026  
**Document Type**: Standalone Technical Manual & Developer Documentation  

---

## 📖 Executive Summary

The **InTime Delivery Platform** backend is a high-performance, asynchronous **FastAPI** application that connects package senders with verified motorcycle dispatch riders across major cities in Nigeria. 

The service operates as a **Meta WhatsApp Cloud API Webhook**, consuming incoming webhook events (text messages, images, template button clicks, and Meta Flow submissions) and driving an automated dispatch, negotiation, and delivery workflow directly within WhatsApp.

This document serves as an exhaustive, standalone technical guide for software engineers, devops practitioners, and system architects.

---

## 📑 Table of Contents

1. [Architecture & System Design](#1-architecture--system-design)
2. [Database Schema & Data Dictionary](#2-database-schema--data-dictionary)
3. [Meta WhatsApp Cloud API Integration](#3-meta-whatsapp-cloud-api-integration)
4. [Core Workflows & State Machines](#4-core-workflows--state-machines)
5. [AI Routing & Conversational Bot ("Femi")](#5-ai-routing--conversational-bot-femi)
6. [Account & Personal Data Deletion (NDPR Compliance)](#6-account--personal-data-deletion-ndpr-compliance)
7. [Background Tasks & Automation Engine](#7-background-tasks--automation-engine)
8. [Phone Number Normalization & Dialing Variations](#8-phone-number-normalization--dialing-variations)
9. [API Endpoint Reference](#9-api-endpoint-reference)
10. [Environment Configuration & Deployment](#10-environment-configuration--deployment)

---

## 1. Architecture & System Design

The application follows an asynchronous event-driven architecture designed for high availability, low latency, and efficient I/O concurrency:

```
                  ┌─────────────────────────────────────────┐
                  │       Meta WhatsApp Cloud API           │
                  └────────────────────┬────────────────────┘
                                       │ (HTTPS Webhook POST / GET)
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │       FastAPI Webhook Server            │
                  │   (Lifespan Manager & Async Routers)    │
                  └─────────┬──────────────┬──────────────┬─┘
                            │              │              │
       ┌────────────────────┘              │              └──────────────────┐
       ▼                                   ▼                                 ▼
┌──────────────┐                 ┌──────────────────┐               ┌─────────────────┐
│ Database Engine              │ Groq AI API      │               │ APScheduler     │
│ PostgreSQL / │                 │ Intent Router &  │               │ 8:00 AM Daily   │
│ SQLite       │                 │ Femi Assistant   │               │ Rider Check-in  │
└──────────────┘                 └──────────────────┘               └─────────────────┘
```

### Technical Stack Components
- **Framework**: FastAPI with `asynccontextmanager` lifespan event handling.
- **Async ORM**: SQLAlchemy 2.0 (`AsyncSession`, `AsyncEngine`) with `asyncpg` for PostgreSQL (Supabase compatibility) and `aiosqlite` for local SQLite development.
- **Database Connection Pooling**: Configured with `statement_cache_size = 0` to work seamlessly with PgBouncer connection pooling.
- **Scheduler**: APScheduler (`AsyncIOScheduler`) with `Africa/Lagos` timezone.
- **LLM Integration**: Groq API (`AsyncGroq`) running Llama 3.3 70B / Llama 3.1 8B models.
- **HTTP Client**: `httpx.AsyncClient` for non-blocking API calls to Meta Graph API.

---

## 2. Database Schema & Data Dictionary

The database consists of 6 primary tables defined in [`models.py`](file:///c:/Users/Ayomide%20Israel/fastAPIforWhatsappwebhook/models.py):

### 2.1 `users`
Stores registered customer accounts.
- `id` (Integer, Primary Key, Index)
- `name` (String, Required): Customer full name.
- `wa_id` (String, Unique, Required): WhatsApp ID / Phone number.
- `display_phone_number` (String, Required): Formatted phone number.
- `phone_number_id` (String, Required): Meta WhatsApp Business Phone Number ID.

### 2.2 `orders`
Stores package delivery transactions and SLA timers.
- `id` (Integer, Primary Key, Index)
- `order_number` (String, Unique, Index): Generated alphanumeric order ID (Format: `ABC1234-XYZ5678`).
- `sender_wa_number` (String, Required): Customer's WhatsApp phone number.
- `rider_wa_number` (String, Nullable): Assigned rider's WhatsApp phone number.
- `recipient_phone_number` (String, Required): Recipient's phone number.
- `package_description` (String, Nullable): Summary of package items.
- `customer_initial_offered_price` (String, Nullable): Initial price offered by customer.
- `final_price_agreed_by_cust_and_rider` (String, Nullable): Agreed delivery fare.
- `status` (String, Required): Order state (`confirmed`, `rider_accepted`, `cancelled`, `expired`, `completed`).
- `pickup_location_name` / `dropoff_location_name` (String, Nullable): Text addresses.
- `pickup_lat`, `pickup_lng`, `dropoff_lat`, `dropoff_lng` (Float, Nullable): GPS coordinates.
- `package_image_id` (String, Nullable): Uploaded package image Meta ID.
- `delivery_progression_status` (String, Nullable): Progress state (`package_picked_up`, `package_delivered`).
- `is_drug`, `is_urgent`, `is_priority` (Boolean, Default False): Medical/priority dispatch flags.
- `sla_expires_by` (DateTime, Timezone UTC): SLA expiration timestamp (30 mins from creation).
- `created_at` (DateTime, Timezone UTC): Timestamp of creation.

### 2.3 `riders`
Stores dispatch rider registry.
- `id` (Integer, Primary Key, Index)
- `first_name`, `last_name` (String, Required): Rider name.
- `rider_wa_number` (String, Required): Primary WhatsApp number.
- `rider_phonenumber_2` (String, Required): Alternate phone number.
- `kyc_status` (String, Required): Verification state (`verified`, `pending`).
- `availability_status` (String, Required): Current dispatch state (`available`, `offline`).

### 2.4 `rider_offers`
Tracks dispatch requests sent to riders.
- `id` (Integer, Primary Key, Index)
- `order_number` (String, Index, Required): Target order.
- `rider_wa_number` (String, Required): Target rider.
- `status` (String, Default "sent"): `sent`, `delivered`, `read`, `viewed`, `accepted`, `declined`.
- `created_at`, `updated_at` (DateTime, Timezone UTC).

### 2.5 `apiRequests`
Webhook payload audit log used for deduplication.
- `id` (Integer, Primary Key, Index)
- `method` (String, Required): `POST`
- `content` (Text, Required): Raw JSON payload body.
- `response` (Text, Required): Processing status response.
- `wamid` (Text, Unique, Index, Nullable): Meta WhatsApp message ID.
- `status_code` (Integer, Required): HTTP status code.
- `date_posted` (DateTime, Timezone UTC).

---

## 3. Meta WhatsApp Cloud API Integration

The webhook interacts with Meta Graph API endpoints via JSON payloads:

### 3.1 Webhook Verification (`GET /webhook`)
Validates Meta verification handshake matching `hub.verify_token` with `VERIFY_TOKEN` env variable.

### 3.2 Webhook Processing (`POST /webhook`)
Handles incoming message types:
1. `statuses`: Updates delivery/read status in `RiderOffer` table.
2. `button`: Handles quick reply button payloads (`Send an Order`, `Delete my Account`, `Contact Support`, `I'm Available`).
3. `interactive`:
   - `button_reply`: Processes button clicks (`FIND_ANOTHER_RIDER:<id>`, `CANCEL_ORDER:<id>`, `CONFIRM_DELETE_ACCOUNT`, `CANCEL_DELETE_ACCOUNT`).
   - `nfm_reply`: Parses Meta Flow responses (`user_registration`, `order_details`, `At_Pickup`, `At_dropoff`, rider acceptance/negotiation).
4. `image`: Uploads package image to active order (`package_image_id`) and triggers rider broadcast.
5. `text`: Routes through Groq Intent Classifier and Femi AI Agent.

---

## 4. Core Workflows & State Machines

### 4.1 Order Creation & Dispatch Workflow

```
Customer Message
      │
      ├──► Registered? ──NO──► Send Registration Flow ──► User Saved
      │         │
      │        YES
      │         ▼
      └──► Send Order Details Flow ──► User Completes Form
                │
                ▼
       Order Status = "confirmed"
                │
                ▼
       Request Package Photo ──► User Uploads Photo
                │
                ▼
       Broadcast to Available Riders
                │
     ┌──────────┴──────────┐
     ▼                     ▼
Rider Accepts        Rider Negotiates
     │                     │
     ▼                     ▼
Rider Assigned       Customer Counter-Offer Prompt
     │
     ▼
Rider Taps "At Pickup" ──► Trigger 10-Min Proximity Check
     │
     ▼
Send 5-Digit Code to Sender, Recipient & Rider
     │
     ▼
Rider Taps "At Dropoff" ──► Order Completed 🏁
```

---

## 5. AI Routing & Conversational Bot ("Femi")

The system leverages Groq API for natural language understanding:

### 5.1 Intent Classifier (`classify_message_intent`)
Utilizes LLM JSON mode with low temperature (0.0) to categorize incoming text into exact intents:
- `CREATE_ORDER`: User wants to send/ship a package.
- `CANCEL_ORDER`: User wants to cancel an order.
- `DELETE_ACCOUNT`: User wants to delete their account or data.
- `TRACK_ORDER`: User asks for delivery status or tracking.
- `MODIFY_ORDER`: User asks to update details.
- `SUPPORT`: User asks for customer support.
- `GENERAL_CHAT`: Greetings, small talk, and general questions.

### 5.2 "Femi" Conversational Agent
- Persona: *Femi*, friendly logistics assistant for InTime.
- History: Multi-turn in-memory chat memory (`_chat_memory`, capped at 10 turns per user).
- Formatting: Auto-converts standard markdown `**bold**` to WhatsApp single-asterisk `*bold*`.
- Steering: Always answers user questions politely while encouraging them to type `Send an Order` to place delivery bookings.

---

## 6. Account & Personal Data Deletion (NDPR Compliance)

To comply with the **Nigeria Data Protection Act (NDPA)** and international privacy standards, users can permanently delete their profile and personal data:

### Triggers
1. **Template Quick Reply**: Tapping the **"Delete my Account"** button in the welcome message.
2. **Natural Text Message**: Typing messages like *"delete my account"*, *"delete my data"*, or *"remove my info"* (classified under `DELETE_ACCOUNT` intent).

### Safety Confirmation Step
To prevent accidental deletions, the system responds with an interactive message containing two buttons:
- **Header/Body**: *"⚠️ Account Deletion Request: Are you sure you want to delete your account? This action will permanently remove your user profile from InTime."*
- **Action Buttons**:
  - `CONFIRM_DELETE_ACCOUNT` (`"🗑️ Yes, Delete"`)
  - `CANCEL_DELETE_ACCOUNT` (`"❌ Cancel"`)

### Execution
When `CONFIRM_DELETE_ACCOUNT` is selected:
1. `delete_user_data(sender_wa_number, db)` removes the user record from the `users` table across all phone number variants.
2. In-memory chat history (`_chat_memory`) is purged.
3. The user receives a confirmation message informing them that their profile has been deleted and that they may re-register at any time by typing *Send an Order*.

---

## 7. Background Tasks & Automation Engine

### 7.1 Daily Cron Job (`scheduler.py`)
- Runs every day at **8:00 AM Lagos Time**.
- Resets all riders' `availability_status` to `"offline"`.
- Sends Meta WhatsApp template `rider_checkin` asking riders to press *"I'm Available"* to re-enroll in daily dispatch.

### 7.2 Non-Blocking Async Timers (`replyhandler.py`)
- `schedule_registration_reminder`: 5-minute reminder if user starts registration but stalls.
- `schedule_user_session_timeout`: 5-minute photo reminder & 15-minute order auto-expiration if package photo is not uploaded.
- `schedule_order_followups`: 1-minute read-count status update & 3-minute fare escalation flow prompt.
- `schedule_customer_offer_timeout`: 4-minute counter-offer reminder.
- `_delayed_pickup_arrival_notifications`: 5 minutes after pickup: checks rider ETA. 10 minutes after pickup: generates a **random 5-digit verification code**, dispatches it to Sender, Recipient, and Rider, and sends the drop-off confirmation Meta Flow to the rider.

---

## 8. Phone Number Normalization & Dialing Variations

Nigerian phone numbers exist in multiple formats (`08151033428`, `+2348151033428`, `2348151033428`, `8151033428`).

- **`normalize_phone_number(phone: str) -> str`**: Converts any Nigerian phone format to canonical E.164 WhatsApp format (`2348151033428`).
- **`get_phone_variants(phone: str) -> list[str]`**: Produces all equivalent string representations for SQL queries (`WHERE phone IN (...)`), guaranteeing user lookups succeed regardless of storage format.

---

## 9. API Endpoint Reference

### `GET /webhook`
- **Purpose**: Meta Webhook verification handshake.
- **Parameters**: `hub.mode`, `hub.challenge`, `hub.verify_token`.
- **Response**: `hub.challenge` plain text (HTTP 200) or HTTP 403 Forbidden.

### `POST /webhook`
- **Purpose**: Primary webhook receiver for WhatsApp events.
- **Payload**: Pydantic validated `apiRequestCreate` model.
- **Response**: `{"status": "ok"}` or `{"status": "duplicate, ignored"}`.

---

## 10. Environment Configuration & Deployment

### Environment Variables (`.env`)
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/intimedb
VERIFY_TOKEN=your_custom_webhook_verification_token
AUTHORIZATION=EAAG...your_meta_access_token
GRAPH_URL=https://graph.facebook.com/v18.0/YOUR_PHONE_NUMBER_ID/messages
GROQ_API_KEY=gsk_your_groq_api_key
```

### Local Development Execution
```bash
# Install dependencies
pip install -r requirements.txt

# Launch FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production Deployment
The application includes a `Procfile` for Heroku / Render / Railway deployment:
```procfile
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```
