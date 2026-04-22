NextXI is a structured amateur football recruitment system developed as a final year project.
It supports role-based interaction for players, clubs, and administrators, allowing clubs to search and rank players, manage shortlists, send trial invitations, record outcomes, generate structured private feedback, and handle reporting and moderation workflows.

Main Features
- Role-based accounts for players, clubs, and administrators
- Structured football-specific player profiles
- Club-side ranked player search with score and rationale
- Shortlist management
- Trial invitation, acceptance, and decline workflow
- Trial outcome recording
- Structured private feedback generation
- Reporting and moderation support
- Suggested players based on recent successful search context

Technologies Used
- Python
- Django
- SQLite
- HTML
- CSS
- Bootstrap

Repository Structure
- core/ – application logic, models, views, forms, templates, static files, and tests
- nextxi/ – Django project configuration
- manage.py – Django management entry point
- db.sqlite3 – SQLite database used for demonstration of the system

Running the Project Locally

 1. Open the project folder
 2.  Open a terminal in the project root (the folder containing manage.py).
 3. Create and activate a virtual environment
    
    python -m venv venv
    
    venv\Scripts\activate
4. Install dependencies
   
    pip install django
5. Apply migrations

    python manage.py migrate
7. Run the development server

   python manage.py runserver
9. Open the system
Open the local address shown in the terminal, usually:

    http://127.0.0.1:8000/


The repository includes db.sqlite3 to support demonstration of the system with existing project data.
Assessment access details and system access instructions are provided in the final report appendix.

Notes:
This repository contains the final submitted version of the project code.
