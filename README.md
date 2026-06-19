# CrisisTwin AI 🚨

> A scalable, AI-powered backend system for complaint management and rapid response coordination.

**CrisisTwin AI** is a robust backend system designed to manage, analyze, and coordinate responses to complaint situations. Built with modern Python technologies, it provides a secure and scalable foundation for reporting emergencies, dispatching responders, and leveraging Artificial Intelligence to automatically categorize, evaluate, and suggest remediation strategies.

---

## ✨ Features

- **Robust User Authentication**: Secure login and registration flows utilizing JSON Web Tokens (JWT).
- **Complaint Reporting System**: Complete RESTful APIs for submitting, tracking, and managing real-time complaint incidents.
- **Role-Based Users**: Architectural readiness for strict access controls (Admin, Responder, Citizen).
- **Scalable Architecture**: Engineered with Domain-Driven Design principles, ensuring the system remains clean and modular as it grows.
- **AI Agent-Ready Design**: Structured with abstract base agents, perfectly primed to integrate Large Language Models (LLMs) for automated complaint analysis.

## 🛠️ Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) - High performance, easy to learn, fast to code.
- **Database**: [PostgreSQL](https://www.postgresql.org/) - Powerful, open-source object-relational database.
- **ORM**: [SQLAlchemy](https://www.sqlalchemy.org/) - The Python SQL toolkit and Object Relational Mapper.
- **Migrations**: [Alembic](https://alembic.sqlalchemy.org/) - Lightweight database migration tool for SQLAlchemy.
- **Language**: Python 3.10+

---

## 📂 Project Structure

```text
complaint_twin_ai/
├── app/
│   ├── agents/         # AI analysis agents and orchestrators
│   ├── api/            # API routers and dependency injection
│   ├── core/           # App-wide settings and security utilities
│   ├── crud/           # Database operations (Create, Read, Update, Delete)
│   ├── db/             # SQLAlchemy engine, session maker, and base class
│   ├── models/         # SQLAlchemy ORM entities
│   ├── schemas/        # Pydantic models for validation and serialization
│   └── services/       # Core business logic and use cases
├── alembic/            # Database migration scripts
├── .env.example        # Template for environment variables
└── requirements.txt    # Python dependencies
```

## 🚀 Setup Instructions

Follow these steps to run the project locally:

**1. Clone the repository**
```bash
git clone https://github.com/yourusername/CrisisTwin.git
cd CrisisTwin/complaint_twin_ai
```

**2. Create a virtual environment**
```bash
python -m venv venv

# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

**3. Install requirements**
```bash
pip install -r requirements.txt
```

**4. Setup Environment Variables**
Copy the example environment file and update it with your actual database credentials and secrets.
```bash
cp .env.example .env
```

**5. Run Database Migrations**
Initialize the database schema using Alembic.
```bash
alembic upgrade head
```

**6. Start the Server**
```bash
uvicorn app.main:app --reload
```

---

## 🔐 Environment Variables

The project requires a `.env` file at the root of `complaint_twin_ai/`. Key variables include:

- `DATABASE_URL`: The connection string for your PostgreSQL database. *(Note: Our project parses this dynamically from components like `POSTGRES_SERVER`, `POSTGRES_USER`, etc.)*
- `SECRET_KEY`: A strong, unpredictable string used to cryptographically sign JWT tokens.
- `ALGORITHM`: The algorithm used for token signing (e.g., `HS256`).

## 📚 API Documentation

Once the server is running, FastAPI automatically generates interactive API documentation based on OpenAPI standards. You can access it by navigating to:

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🔮 Future Improvements

As the project evolves, the following features are mapped for the roadmap:

- **AI Complaint Analysis Agents**: Integration with Large Language Models (LLMs) to automatically parse descriptions, assess severity, and extract key entities from incoming reports.
- **Real-Time Alerts**: WebSocket integration for instant push notifications and alerts to active responders.
- **External API Integrations**: Hooking into weather data, traffic APIs, and emergency broadcast systems for enriched complaint context.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
