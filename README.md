# Nigerian Health Diagnosis System

A Web-Based Automated Symptom Diagnosis and Patient Recommendation System using Hybrid AI (Rule-Based + Naive Bayes) tailored for the Nigerian healthcare context.

## Features

- **User Side**: Registration, Login, Symptom Checker, Diagnosis Results, Medical History, Profile Management
- **Admin Side**: Registration (with code), Login, Dashboard, Disease Management, Symptom Management, Rule Management, User Management, System Settings, Reports
- **Hybrid AI Engine**: Combines Rule-Based reasoning with Naive Bayes Machine Learning
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Secure**: Password hashing with salt, session management

## Installation

1. Install Python 3.8+
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the application:
   ```
   python app.py
   ```
4. Open browser and go to: `http://localhost:5000`

## Default Admin Registration Code

- **Code**: `ADMIN2024`

## System Architecture

- **Backend**: Python Flask
- **Database**: SQLite (auto-created on first run)
- **Frontend**: HTML5, CSS3, JavaScript
- **AI Engine**: Hybrid (Rule-Based + Naive Bayes)

## Supported Diseases

1. Malaria
2. Typhoid Fever
3. Influenza
4. Pneumonia
5. Common Cold
6. Gastroenteritis
7. Dengue Fever
8. COVID-19

## Database Schema

- users
- symptoms
- diseases
- disease_symptom_rules
- patient_symptom_input
- diagnosis_results
- recommendations
- system_settings

## Author

Chisom - Academic Project
