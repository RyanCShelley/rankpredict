# RankPredict v2 - Complete Rebuild

A two-screen SEO tool that helps users identify winnable keywords and generate SERP-driven content recommendations. The tool is dynamic and data-driven—no generic templates or boilerplate recommendations.

## Project Structure

```
rankpredict-v2/
├── backend/
│   ├── app/
│   │   ├── api/          # API endpoints
│   │   ├── models/        # Database models
│   │   ├── services/     # Business logic services
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── database.py   # Database setup
│   │   └── main.py       # FastAPI app
│   ├── models/           # ML model files
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/        # React pages
│   │   ├── components/   # React components
│   │   ├── services/     # API clients
│   │   └── contexts/     # React contexts
│   └── package.json
└── README.md
```

## Features

### Screen 1: Strategy Dashboard
- **Keyword List Management**: Create and manage keyword lists with target domain URLs
- **Rankability Scoring**: Score keywords using ML model based on likelihood to rank
- **Keyword Selection**: Select keywords and designate as new or existing content
- **Persistence**: All data saved to SQLite database

### Screen 2: Outline Builder / Content Refresher
- **Dynamic Outline Generation**: SERP-driven outlines (NO TEMPLATES)
- **Intent Analysis**: LLM-powered intent extraction and content format recommendations
- **Content Refresh Mode**: Compare existing content against SERP, identify gaps
- **Improvement Plans**: Specific, actionable improvement recommendations

## Technology Stack

- **Backend**: FastAPI, SQLAlchemy, SQLite
- **Frontend**: React, Vite, Tailwind CSS
- **ML**: scikit-learn, joblib
- **SERP**: SERPAPI
- **LLM**: OpenAI API or Hugging Face (for intent analysis)
- **Semantic**: sentence-transformers (all-MiniLM-L6-v2)

## Setup Instructions

### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file in `backend/` directory:
```env
SERPAPI_KEY=your_serpapi_key
SERANKING_KEY=your_seranking_key
OPENAI_API_KEY=your_openai_key  # Optional, for intent analysis
HUGGINGFACE_API_KEY=your_hf_key  # Optional, fallback for intent analysis
SECRET_KEY=your_secret_key_for_jwt
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

5. Run the backend:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create `.env` file in `frontend/` directory:
```env
VITE_API_BASE_URL=http://localhost:8000
```

4. Run the frontend:
```bash
npm run dev
```

## Default Login Credentials

- **Username**: `ryan@smamarketing`
- **Password**: `NCH3250fl`

## Key Implementation Details

### No Templates Policy
- Every outline is generated dynamically based on SERP analysis
- Each keyword gets a unique outline structure
- Outlines vary based on what's actually ranking

### Rankability Scoring
- Uses ML model: `rf_model_top10_v2_20251208_2022.pkl`
- 15 features from `feature_cols_v2.json`
- Returns rankability score (0-1) and opportunity tier (HIGH/MEDIUM/LOW)

### Database Persistence
- SQLite database: `backend/rankpredict_v2.db`
- All keyword lists, scores, and outlines are persisted
- SERP analysis is cached to avoid redundant API calls

## API Endpoints

### Strategy Dashboard
- `POST /api/strategy/lists` - Create keyword list
- `GET /api/strategy/lists` - Get all lists
- `GET /api/strategy/lists/{id}` - Get specific list
- `POST /api/strategy/lists/{id}/score` - Score keywords
- `PATCH /api/strategy/keywords/{id}` - Update keyword
- `DELETE /api/strategy/lists/{id}` - Delete list

### Outline Builder
- `GET /api/outline/keywords` - Get selected keywords
- `POST /api/outline/generate` - Generate outline
- `GET /api/outline/improvement-plan/{id}` - Get improvement plan

### Authentication
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Get current user

## Development Notes

- Model files must be in `backend/models/`:
  - `rf_model_top10_v2_20251208_2022.pkl`
  - `feature_cols_v2.json`
- Database is automatically initialized on first run
- SERP data is cached in `KeywordAnalysis` table
- Semantic similarity uses sentence-transformers model

## License

© 2024 SMA Marketing. All rights reserved.

