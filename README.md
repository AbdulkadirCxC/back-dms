# Dental Management System (DMS)

A RESTful API backend for managing a dental clinic, built with Django REST Framework. Based on the schema from `dental_management_system_sample.pdf`.

## Features

- **Patients** – Patient records (name, gender, DOB, phone)
- **Dentists** – Dentist profiles with specialization
- **Appointments** – Schedule patient appointments (Scheduled, Completed, Cancelled)
- **Treatments** – Treatment catalog with name, description, cost
- **Patient Treatments** – Records of treatments performed (with optional cost override)
- **Invoices** – Patient invoices (Paid, Unpaid, Partial)
- **Payments** – Payment records (EVC Plus, Cash, Card, etc.)
- **JWT Authentication** – Secure API with token-based auth

## Quick Start

### 1. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run migrations

```bash
python manage.py migrate
```

### 4. Create superuser (for admin & API auth)

```bash
python manage.py createsuperuser
```

### 5. Run the server

```bash
python manage.py runserver
```

Visit:
- **API Root**: http://127.0.0.1:8000/api/
- **Admin**: http://127.0.0.1:8000/admin/

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/auth/token/` | Obtain JWT token (username, password) |
| `POST /api/auth/refresh/` | Refresh JWT token |
| `GET/POST /api/patients/` | List/create patients |
| `GET/POST /api/dentists/` | List/create dentists |
| `GET/POST /api/appointments/` | List/create appointments |
| `GET/POST /api/treatments/` | List/create treatments |
| `GET/POST /api/patient-treatments/` | List/create patient treatment records |
| `GET/POST /api/invoices/` | List/create invoices |
| `GET/POST /api/payments/` | List/create payments |

All resources support `GET /{id}/`, `PUT /{id}/`, `PATCH /{id}/`, `DELETE /{id}/`.

### Filtering

- **Appointments**: `?patient=1`, `?dentist=1`, `?status=Scheduled`
- **Patient Treatments**: `?patient=1`, `?treatment=1`, `?dentist=1`
- **Invoices**: `?patient=1`, `?status=Paid`
- **Payments**: `?invoice=1`, `?method=EVC Plus`

## Database Schema (from PDF)

| Table | Key Fields |
|-------|------------|
| Patients | full_name, gender, date_of_birth, phone |
| Dentists | name, specialization |
| Appointments | patient, dentist, appointment_date, status |
| Treatments | name, description, cost |
| Patient Treatments | patient, treatment, dentist, date, cost_override |
| Invoices | patient, total_amount, status |
| Payments | invoice, amount, method, payment_date |

## Project Structure

```
back-DMS/
├── core/           # Django project config
├── dental/         # Dental Management app (models, views, serializers)
├── manage.py
└── requirements.txt
```
