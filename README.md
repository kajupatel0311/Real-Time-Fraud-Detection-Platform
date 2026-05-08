# FraudSentinel

FraudSentinel is a real-time transaction monitoring and fraud detection platform. It uses a hybrid approach, combining machine learning (XGBoost) with behavioral heuristics to identify suspicious activity, restrict transactions, and alert administrators.

## Architecture Summary
The system consists of a FastAPI backend for real-time inference and data persistence, a React Native mobile application for on-the-go monitoring, and a responsive web dashboard for operational oversight.

## Features
- **Hybrid Fraud Scoring**: Combines an XGBoost ML model with a heuristic behavioral engine.
- **Behavioral Analysis**: Tracks transaction bursts, account depletion rates, and high-risk merchant interactions.
- **Mobile Application**: A React Native (Expo) app for monitoring alerts and analyzing transactions via a conversational interface.
- **Persistent Storage**: Utilizes SQLite to maintain an audit trail of all transactions and high-risk alerts.
- **Real-Time Alerts**: Flags critical transactions and exposes them via dedicated API endpoints.

## Tech Stack
- **Backend**: Python, FastAPI, Uvicorn
- **Machine Learning**: XGBoost, Scikit-learn, Pandas, Numpy
- **Database**: SQLite
- **Web Frontend**: HTML5, Vanilla CSS, Vanilla JS
- **Mobile Frontend**: React Native, Expo
- **Deployment**: Render (Backend), Vercel (Web Frontend)

## Installation

### Backend Setup
1. Clone the repository.
2. Navigate to the `backend` directory.
3. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   pip install -r requirements.txt
   ```

### Web Frontend Setup
The web frontend is served statically by the FastAPI backend during local development. No separate installation is required unless deploying to Vercel.

### Mobile App Setup
1. Navigate to the `mobile` directory.
2. Install dependencies:
   ```bash
   npm install
   ```

## Running Locally

### Backend & Web Dashboard
Start the FastAPI server from the `backend` directory:
```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```
The web dashboard will be available at `http://127.0.0.1:8000/`.

### Mobile Application
Start the Expo development server from the `mobile` directory:
```bash
npx expo start
```

## Deployment

### Render Backend Deployment
The backend is configured for deployment on Render using the provided `render.yaml` file. It provisions a Python web service and attaches a persistent disk for the SQLite database.
1. Connect your repository to Render.
2. Render will automatically detect the `render.yaml` blueprint.

### Vercel Frontend Deployment
The contents of the `web` directory can be deployed as a static site on Vercel. Ensure you configure the API endpoints in `web/static/app.js` to point to your production Render URL.

## API Endpoints
- `POST /predict`: Submit a structured transaction for risk analysis.
- `POST /chat_predict`: Submit a natural language transaction description for parsing and risk analysis.
- `GET /history`: Fetch the persistent audit trail of analyzed transactions.
- `GET /alerts`: Retrieve active high-risk alerts and metadata.
- `GET /health`: Monitor engine status, uptime, and processing volume.

## Project Structure
```text
.
├── backend/            # Core backend services
│   ├── api/            # FastAPI application, database logic, and feature engineering
│   ├── src/            # Model training, data pipelines, and drift monitoring
│   ├── render.yaml     # Render deployment configuration
│   └── requirements.txt# Production dependencies
├── mobile/             # React Native (Expo) application
│   ├── screens/        # UI screens (Dashboard, Chat, Alerts, History)
│   ├── services/       # API communication layer
│   └── styles/         # Global theme definitions
├── web/                # Web frontend assets
│   ├── static/         # CSS and client-side JavaScript
│   └── templates/      # HTML views
├── models/             # Serialized ML models and preprocessors
├── data/               # Persistent storage (SQLite) and datasets
├── docs/               # Architecture diagrams and documentation
└── tests/              # Validation suites and test cases
```

## Future Improvements
- **PostgreSQL**: Migrate from SQLite to PostgreSQL for distributed environments.
- **Kafka**: Implement Kafka for high-throughput, asynchronous event streaming.
- **Redis**: Add Redis for low-latency feature stores and rate limiting.
- **WebSocket Streaming**: Enable real-time alert pushes to the web and mobile clients.
