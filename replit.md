# InstaMonitor Pro

## Overview

InstaMonitor Pro is an Instagram lead generation and monitoring application that tracks followers of target Instagram accounts. The system scrapes Instagram data using the HikerAPI, stores leads in a SQLite database, and provides a React-based dashboard for managing and analyzing potential leads. The application focuses on finding and tracking users who follow specific Instagram accounts, extracting contact information and profile details for lead generation purposes.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture

**Technology Stack:** React 18.2 with Vite as the build tool and development server.

**Styling Solution:** TailwindCSS 3.3 with PostCSS and Autoprefixer for utility-first CSS styling. This provides rapid UI development with minimal custom CSS.

**UI Components:** Uses Lucide React (v0.263.1) for iconography, providing a consistent and lightweight icon set throughout the application.

**Development Server:** Vite configured to run on host `0.0.0.0` port 5000, enabling network access and strict port enforcement. API requests are proxied to the backend server running on port 8000, eliminating CORS issues during development.

### Backend Architecture

**Web Framework:** Flask-based Python backend with CORS enabled for cross-origin requests from the React frontend.

**API Design:** RESTful API structure with endpoints prefixed under `/api` route for clear separation between frontend and backend concerns.

**Concurrency Model:** Background job processing using Python threading for long-running Instagram scraping operations. Jobs run asynchronously while providing real-time status updates through the API.

**Status Tracking:** In-memory job status dictionary (`JOBS`) tracks running scraping operations with progress metrics including status, found leads count, total followers, and status messages.

**Rate Limiting:** Implements random delays (1.5-3.0 seconds) between API calls to Instagram to avoid rate limiting and detection.

**Authentication:** Simple password-based authentication (`APP_PASSWORD`) for protecting sensitive operations.

### Data Storage

**Database:** SQLite3 for lightweight, serverless data persistence.

**Schema Design:**
- **targets table:** Stores monitored Instagram accounts with username (primary key) and last scrape timestamp
- **leads table:** Comprehensive storage of discovered users including:
  - Profile identifiers (pk, username)
  - Profile information (full_name, bio, email)
  - Metrics (followers_count, is_private)
  - Tracking metadata (source_account, found_date, last_scraped_date, status)
  - Change tracking (change_details) for monitoring profile updates
  - Export tracking (last_exported) for data pipeline management

**Data Export:** JSON export functionality to bridge backend data with frontend (`users.json` in `src/data/`), enabling static data consumption in the React application.

**Rationale:** SQLite chosen for simplicity, zero-configuration deployment, and adequate performance for single-user/small-team lead generation workflows. The file-based nature eliminates database server dependencies.

### External Dependencies

**HikerAPI Integration:** Third-party Instagram scraping service accessed via the `hikerapi` Python client library.

**API Key Management:** Hardcoded API key (`y0a9buus1f3z0vx3gqodr8lh11vvsxyh`) for HikerAPI authentication. This should be moved to environment variables for production security.

**Instagram Data Access:**
- `user_following_chunk_gql`: GraphQL-based pagination method for retrieving follower lists
- Cursor-based pagination for handling large follower sets
- User profile detail extraction including bio, email, and engagement metrics

**Pros of HikerAPI approach:**
- Abstracts Instagram's complex and frequently-changing API
- Handles authentication and session management
- Provides structured data responses

**Cons and Considerations:**
- Dependency on third-party service availability and pricing
- Risk of API changes or service discontinuation
- Rate limiting constraints from both HikerAPI and Instagram
- Potential Terms of Service concerns with Instagram data scraping

**Process Orchestration:** Concurrently package manages parallel execution of Vite dev server and Flask backend with color-coded console output for easier debugging.