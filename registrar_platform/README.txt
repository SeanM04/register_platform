UniStudio Bot — Setup & Usage Guide
=====================================
Official academic chatbot for Manicaland State University of Applied Sciences (MSUAS)

NOTE
----
This repository now includes a production-facing UniStudio chatbot inside the Django
platform UI. The files in `registrar_platform/` remain a standalone prototype for
terminal usage and experimentation.

REQUIREMENTS
------------
- Python 3.10 or higher
- An OpenAI API key: In have inserted it. 
- The two MSUAS data files:
    course_final_marks.csv
    registration.csv


INSTALLATION
------------
1. Install required packages for the standalone prototype:

       pip install -r "requirements 3.txt"

2. Set the two CSV paths as environment variables before running the prototype:

       PowerShell:
           $env:UNISTUDIO_MARKS_CSV="C:\path\to\your\course_final_marks.csv"
           $env:UNISTUDIO_REGISTER_CSV="C:\path\to\your\registration.csv"

   On Mac/Linux use:
           export UNISTUDIO_MARKS_CSV="/home/user/course_final_marks.csv"
           export UNISTUDIO_REGISTER_CSV="/home/user/registration.csv"

3. Set your OpenAI API key as an environment variable:

       Windows:   set OPENAI_API_KEY=sk-...
       Mac/Linux: export OPENAI_API_KEY=sk-...


RUNNING THE BOT
---------------
    python unistudio_chatbot.py

The bot will load the data, greet you, ask your name, and then
you can start asking questions.

Built-in commands (type these at any time):
    help      Show available commands
    stats     Show live database summary
    history   Show this session's conversation
    quit      Exit the bot


AZURE UPGRADE (Future)
----------------------
When the platform moves to Azure Table Storage, only two methods
need to change inside the DataLoader class in unistudio_bot.py:

    _load_registrations()   — currently reads registration.csv
    _load_marks()           — currently reads course_final_marks.csv

Replace the CSV reading logic in those two methods with Azure
Table Storage queries using the connection string provided by
the platform administrator. Everything else — all calculations,
tools, memory, and the chat engine — stays exactly the same.

The Azure connection details are already in the file as comments:

    # AZURE_CONNECTION_STRING = (
    #     "DefaultEndpointsProtocol=https;..."
    # )
    # TABLE_NAME = "LoanData"

Uncomment and configure those lines, then update the two loader
methods to use TableServiceClient from the azure-data-tables package:

    pip install azure-data-tables


FILES IN THIS PACKAGE
---------------------
    unistudio_chatbot.py  Main chatbot — run this
    requirements 3.txt    Standalone prototype dependencies
    README.txt            This file
    unistudio_memory.db   Created automatically on first run (conversation memory)


EXAMPLE QUESTIONS
-----------------
See the EXAMPLE PROMPTS section below for a full list of things
you can ask the bot.


================================================================
EXAMPLE PROMPTS — WHAT TO ASK UNISTUDIO BOT
================================================================

PROGRAMME PERFORMANCE
---------------------
- What is the pass rate for BCom Accounting?
- Which programme has the highest pass rate?
- Which programme has the lowest average mark?
- Give me a full breakdown of the BSc Information Systems programme.
- How does BCom Business Management compare to BCom Accounting?
- Compare all Engineering programmes by pass rate.
- What is the pass rate for Mining and Mineral Processing in August 2025?
- Which is the most enrolled programme at MSUAS?
- How many students are in the BCom Tourism and Hospitality programme?

STUDENT LOOKUP
--------------
- Look up student M22CRF.
- What is the academic history of student M23BJJ?
- What decisions has student M22CPM received across all semesters?
- What is the completion rate for student M22CRF in March 2025?
- Is student M247KI at academic risk?
- What degree classification is student M22CMM on track for?

CALCULATIONS
------------
- A student has marks 45, 60, 55, 40, 70. What is their completion rate?
- If a student fails 4 out of 6 courses, what happens to their completion?
- What mark does a student need to achieve a 2.1 classification?
- Explain the completion calculation rules at MSUAS.
- What is the difference between a Repeat and a Retake decision?
- A student has a Deferred decision. What does that mean for their completion?

AT-RISK STUDENTS
----------------
- How many students are currently at academic risk?
- Show me all critical risk students.
- Which faculty has the most at-risk students?
- How many students in the Engineering faculty are on Retake?
- List students with a Repeat Level decision.
- How many students are presumed withdrawn?
- What percentage of students are proceeding normally?

DEMOGRAPHICS & STATISTICS
--------------------------
- What is the gender breakdown across all programmes?
- How many male vs female students are in BCom Accounting?
- Which programme has the most female students?
- What is the overall average mark across all students?
- What is the overall pass rate at MSUAS?
- How many students are registered in the current semester?
- What are the academic periods covered in the database?

ACADEMIC DECISIONS
------------------
- Break down all academic decisions for the August 2025 semester.
- How many students received a Proceed Carrying decision?
- What does Supplement and Review mean?
- How many students are carrying courses into the next semester?
- What is the most common academic decision at MSUAS?

FACULTY COMPARISONS
-------------------
- Compare the Engineering faculty and the Agri-business faculty.
- Which faculty has the best overall pass rate?
- How many students are in the Applied Social Sciences faculty?
- What programmes fall under the Applied Sciences and Technology faculty?

HARDEST AND EASIEST COURSES
----------------------------
- Which courses have the lowest average marks?
- What is the hardest course in the Engineering programme?
- Which courses do students score highest in?
- What is the average mark for Strength of Materials?

ADMISSIONS & GENERAL UNIVERSITY INFO
--------------------------------------
- How do I apply to MSUAS?
- What are the entry requirements for Engineering?
- What O-Level subjects do I need to study at MSUAS?
- What postgraduate programmes does MSUAS offer?
- Are there any short courses available?
- Where is MSUAS located?
- How do I get to MSUAS from Harare?
- What is the MSUAS phone number?
- What is the MSUAS email address?
- Is there student accommodation on campus?
- Does MSUAS have a library?
- What is the grading scale at MSUAS?
- How long does a BCom degree take to complete?
- How long does an Engineering degree take?
- What is the August 2026 intake about?
- How do I access the student portal?
- Where do I pay my fees?
- Does MSUAS have health services?
================================================================
