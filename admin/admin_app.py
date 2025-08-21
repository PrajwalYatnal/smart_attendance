from flask import Flask, render_template, request,Response, redirect, url_for, flash, session, send_file
from pymongo import MongoClient
import re
import os
import cv2
import base64
import face_recognition
import numpy as np
import json
import datetime
from bson import ObjectId
from collections import defaultdict
import pandas as pd
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)

# MongoDB Setup
client = MongoClient("mongodb://localhost:27017/")
db = client["face_db"]
admins = db["admins"]
students = db["students"]
teachers = db["teachers"]
class_sessions = db["class_sessions"]
attendance_db = db["attendance"]
exam_dates = db["exam_dates"]
# Admin folder paths
app.template_folder = os.path.join(os.path.dirname(__file__), 'templates')
app.static_folder = os.path.join(os.path.dirname(__file__), 'static')


import re
@app.route('/admin/signup', methods=['GET', 'POST'])
def admin_signup():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        admin_id = request.form['admin_id']

        # Check if name contains any digit
        if any(char.isdigit() for char in name):
            flash("Name cannot contain numbers.", "error")
            return redirect(url_for('admin_signup'))

        # Check admin ID format
        if not admin_id.startswith("AD"):
            flash("Admin ID must start with AD.", "error")
            return redirect(url_for('admin_signup'))

        # Check if passwords match
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for('admin_signup'))

        # Check password strength
        if len(password) < 7 or \
           not re.search(r'[A-Z]', password) or \
           not re.search(r'[a-z]', password) or \
           not re.search(r'\d', password) or \
           not re.search(r'[\W_]', password):
            flash("Password must be at least 7 characters long and include uppercase, lowercase, number, and special character.", "error")
            return redirect(url_for('admin_signup'))

        # Check if username already exists
        if admins.find_one({"username": username}):
            flash("Username already exists. Please choose another.", "error")
            return redirect(url_for('admin_signup'))

        # Insert new admin
        admins.insert_one({
            "name": name,
            "username": username,
            "password": password,
            "admin_id": admin_id
        })

        flash("Signup successful! You can now log in.", "success")
        return redirect(url_for('admin_login'))

    return render_template('signup.html')



@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        admin = admins.find_one({"username": username, "password": password})
        if admin:
            session['admin_name'] = admin['name']
            flash(f"Welcome, {admin['name']}!", "success")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid credentials", "error")
            return redirect(url_for('admin_login'))

    return render_template('login.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_name' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('admin_login'))

    total_students = students.count_documents({})
    total_teachers = teachers.count_documents({})

    total_sessions_result = class_sessions.aggregate([
        {"$project": {"count": {"$size": "$sessions"}}},
        {"$group": {"_id": None, "total": {"$sum": "$count"}}}
    ])
    total_sessions = list(total_sessions_result)
    total_sessions = total_sessions[0]['total'] if total_sessions else 0

    all_classes = teachers.distinct("classes")
    all_subjects = teachers.distinct("subjects")

    return render_template('dashboard.html',
                           name=session['admin_name'],
                           total_students=total_students,
                           total_teachers=total_teachers,
                           total_sessions=total_sessions,
                           unique_classes=len(set(all_classes)),
                           unique_subjects=len(set(all_subjects)))



@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('admin_login'))


@app.route('/admin/register-student', methods=['GET', 'POST'])
def register_student():
    if 'admin_name' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        name = request.form['name']
        student_id = request.form['student_id']
        Year = request.form['Year']
        branch = request.form['branch']
        email = request.form['email']
        phone = request.form['phone']
        login_id = request.form['login_id']
        password = request.form['password']

        # Validations
        if any(char.isdigit() for char in name):
            flash("Name cannot contain numbers.", "error")
            return redirect(url_for('register_student'))

        if not student_id.startswith("2SD"):
            flash("Student ID must start with 2SD.", "error")
            return redirect(url_for('register_student'))

        if not (email.endswith("@gmail.com") or email.endswith("@yahoo.com")):
            flash("Email must end with @gmail.com or @yahoo.com.", "error")
            return redirect(url_for('register_student'))

        if not (phone.isdigit() and len(phone) == 10):
            flash("Phone number must be exactly 10 digits and contain only numbers.", "error")
            return redirect(url_for('register_student'))

        if students.find_one({"student_id": student_id}):
            flash("Student ID already exists. Please use a different one.", "error")
            return redirect(url_for('register_student'))

        if students.find_one({"login_id": login_id}):
            flash("Login ID is already taken. Please choose another.", "error")
            return redirect(url_for('register_student'))

        # Store valid student data temporarily in session
        session['student_data'] = {
            "name": name,
            "student_id": student_id,
            "Year": Year,
            "branch": branch,
            "email": email,
            "phone": phone,
            "login_id": login_id,
            "password": password,
            "student_id_str": str(student_id)
        }
        return redirect(url_for('capture_student_face'))

    return render_template('register_student.html')



@app.route('/admin/capture-student-face')
def capture_student_face():
    student_data = session.get('student_data')

    if not student_data:
        flash("No student data found. Please try again.", "error")
        return redirect(url_for('register_student'))

    cap = cv2.VideoCapture(0)
    duplicate_face_detected = False

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        if face_encodings:
            encoding = face_encodings[0]
            _, buffer = cv2.imencode('.jpg', frame)
            img_str = base64.b64encode(buffer).decode('utf-8')

            # Check for duplicate face encoding in the database
            existing_faces = students.find()
            existing_encodings = [student['face_encoding'] for student in existing_faces if 'face_encoding' in student]

            def is_duplicate_face(new_encoding, existing_encodings):
                for encoding in existing_encodings:
                    matches = face_recognition.compare_faces([encoding], new_encoding)
                    if matches[0]:
                        return True
                return False

            if is_duplicate_face(encoding, existing_encodings):
                flash("This face is already registered.", "error")
                duplicate_face_detected = True
                break

            student_data['face_encoding'] = encoding.tolist()
            student_data['image'] = img_str
            # The above code is adding a new key-value pair to the `student_data` dictionary. The key
            # is 'timestamp' and the value is the current date and time obtained using the
            # `datetime.datetime.now()` function.
                # student_data['timestamp'] = datetime.datetime.now()

            students.insert_one(student_data)
            session.pop('student_data', None)
            flash("Student registered successfully!", "success")
            break

        cv2.imshow("Capture Student Face (Press Q to exit)", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    if duplicate_face_detected:
        return redirect(url_for('register_student'))
    else:
        return redirect(url_for('admin_dashboard'))
    
@app.route('/admin/register-teacher', methods=['GET', 'POST'])
def register_teacher():
    if 'admin_name' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        name = request.form['name']
        teacher_id = request.form['teacher_id']
        department = request.form['department']
        email = request.form['email']
        login_id = request.form['login_id']
        password = request.form['password']

        subjects = request.form['subjects'].split(',')
        subjects = [s.strip() for s in subjects if s.strip()]

        classes = request.form['classes'].split(',')
        classes = [c.strip() for c in classes if c.strip()]
        
        if teachers.find_one({"teacher_id": teacher_id}):
            flash("Teacher ID already exists. Please use a different one.", "error")
            return redirect(url_for('register_teacher'))

        session['teacher_data'] = {
            "name": name,
            "teacher_id": teacher_id,
            "department": department,
            "email": email,
            "login_id": login_id,
            "password": password,
            "subjects": subjects,
            "classes": classes,
            "teacher_id_str": str(teacher_id)
        }
        return redirect(url_for('capture_teacher_face'))

    return render_template('register_teacher.html')

@app.route('/admin/capture-teacher-face')
def capture_teacher_face():
    teacher_data = session.get('teacher_data')

    if not teacher_data:
        flash("No teacher data found. Please try again.", "error")
        return redirect(url_for('register_teacher'))

    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        if face_encodings:
            encoding = face_encodings[0]
            _, buffer = cv2.imencode('.jpg', frame)
            img_str = base64.b64encode(buffer).decode('utf-8')

            # Check for duplicate face encoding
            # Combine encodings from both teachers and students
            teacher_faces = teachers.find()
            student_faces = students.find()

            def is_duplicate_face(new_encoding):
                # Check against students
                for s in student_faces:
                    if 'face_encoding' in s:
                        match = face_recognition.compare_faces([s['face_encoding']], new_encoding)
                        if match[0]:
                            return "student"
                
                # Check against teachers
                for t in teacher_faces:
                    if 'face_encoding' in t:
                        match = face_recognition.compare_faces([t['face_encoding']], new_encoding)
                        if match[0]:
                            return "teacher"
                
                return None

            duplicate_type = is_duplicate_face(encoding)

            if duplicate_type == "student":
                flash("This face is already registered as a student. Cannot register as a teacher.", "error")
                cap.release()
                cv2.destroyAllWindows()
                return redirect(url_for('admin_dashboard'))

            elif duplicate_type == "teacher":
                flash("This face is already registered as a teacher.", "error")
                cap.release()
                cv2.destroyAllWindows()
                return redirect(url_for('admin_dashboard'))

            teacher_data['face_encoding'] = encoding.tolist()
            teacher_data['image'] = img_str
            # teacher_data['timestamp'] = datetime.datetime.now()

            teachers.insert_one(teacher_data)
            session.pop('teacher_data', None)
            flash("Teacher registered successfully!", "success")
            break

        cv2.imshow("Capture Teacher Face (Press Q to cancel)", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/generate-report', methods=['GET', 'POST'])
def admin_generate_report():
    if 'admin_name' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('admin_login'))

    # Populate dropdown with unique class-subject pairs
        # Unique class-subject pairs for dropdown
    class_subject_set = set()
    for doc in class_sessions.find({}, {"class": 1, "subject": 1, "_id": 0}):
        class_subject_set.add((doc['class'], doc['subject']))

    dropdown_options = sorted(list(class_subject_set))  # list of tuples: (class, subject)


    if request.method == 'POST':
        class_subject = request.form['class_subject']
        class_name, subject = class_subject.split("__")
        exam_type = request.form['exam_type']
        sessions = class_sessions.find({"class": class_name, "subject": subject})

        session_ids = []
        for doc in sessions:
            for s in doc.get('sessions', []):
                session_ids.append(s['session_id'])

        attendance_records = list(attendance_db.find({
            "class": class_name,
            "subject": subject,
            "session_id": {"$in": session_ids}
        }))

        students_list = list(students.find({"Year": "Year " + class_name}))
        student_names = {s['student_id']: s['name'] for s in students_list}
        student_attendance = defaultdict(list)

        for student_id in student_names:
            student_attendance[student_id] = []

        for record in attendance_records:
            attendance_map = {entry['student_id']: entry['present'] for entry in record['attendance']}
            for student_id in student_names:
                student_attendance[student_id].append(attendance_map.get(student_id, False))

        eligibility_criteria = {'IA1': 65, 'IA2': 75, 'IA3': 85, 'SEE': 75}
        headers = ['Student Name'] + [f"Class-{i+1}" for i in range(len(session_ids))] + ['Attendance %', 'Eligible']

        report_rows = []
        for student_id, presence_list in student_attendance.items():
            name = student_names.get(student_id, "Unknown")
            total = len(presence_list)
            present = sum(presence_list)
            percent = round((present / total) * 100, 2) if total else 0
            eligible = "Yes" if percent >= eligibility_criteria[exam_type] else "No"
            row = [name] + ['Present' if p else 'Absent' for p in presence_list] + [percent, eligible]
            report_rows.append(row)

        df = pd.DataFrame(report_rows, columns=headers)

        folder = 'admin_reports'
        if not os.path.exists(folder):
            os.makedirs(folder)

        filename = f"{class_name}_{subject}_{exam_type}_admin_report.xlsx"
        filepath = os.path.join(folder, filename)

        if os.path.exists(filepath):
            os.remove(filepath)

        df.to_excel(filepath, index=False)

        flash(f"Report generated and saved as {filename}", "success")
        return render_template("admin_report.html", df=df.to_html(classes="table", index=False), filename=filename)

    return render_template('admin_generate_report.html', dropdown_options=dropdown_options)

@app.route('/admin/manage-users', methods=['GET', 'POST'])
def manage_users():
    if 'admin_name' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('admin_login'))

    # Fetch all students and teachers
    all_students = list(students.find({}))
    all_teachers = list(teachers.find({}))

    return render_template('manage_users.html', students=all_students, teachers=all_teachers)

@app.route('/admin/delete-user/<role>/<user_id>', methods=['POST'])
def delete_user(role, user_id):
    if 'admin_name' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('admin_login'))

    collection = students if role == 'student' else teachers
    result = collection.delete_one({"_id": ObjectId(user_id)})

    if result.deleted_count:
        flash(f"{role.capitalize()} deleted successfully!", "success")
    else:
        flash(f"Failed to delete {role}.", "error")

    return redirect(url_for('manage_users'))


@app.route('/admin/attendance-overview', methods=['GET', 'POST'])
def attendance_overview():
    if 'admin_name' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('admin_login'))

    classes = sorted(set([s['Year'].split()[-1] for s in students.find()]))
    subjects = sorted(set([record['subject'] for record in attendance_db.find()]))

    selected_class = request.form.get('class_name')
    selected_subject = request.form.get('subject')
    session_id = request.form.get('session_id')
    attendance_data = []
    session_options = []

    # Fetch IA exam dates from MongoDB
    exam_doc = exam_dates.find_one()
    ia_dates = {
        "IA1": exam_doc.get("IA1") if exam_doc else None,
        "IA2": exam_doc.get("IA2") if exam_doc else None,
        "IA3": exam_doc.get("IA3") if exam_doc else None,
        "SEE": exam_doc.get("SEE") if exam_doc else None,
    }

    # Collect sessions for dropdown
    if selected_class and selected_subject:
        session_doc = class_sessions.find_one({
            "class": selected_class,
            "subject": selected_subject
        })

        if session_doc and 'sessions' in session_doc:
            for s in session_doc['sessions']:
                timestamp = s['timestamp']
                # Check if this session is before any completed IA
                is_disabled = any(ia_date and timestamp < ia_date and datetime.utcnow() > ia_date for ia_date in ia_dates.values())
                session_options.append({
                    "session_id": s['session_id'],
                    "timestamp": timestamp.strftime('%Y-%m-%d %H:%M'),
                    "disabled": is_disabled
                })

    # If a session was selected, validate its timestamp
    if request.method == 'POST' and session_id:
        session_doc = class_sessions.find_one({
            "class": selected_class,
            "subject": selected_subject
        })
        selected_session = next((s for s in session_doc.get('sessions', []) if s['session_id'] == session_id), None)

        if selected_session:
            session_time = selected_session['timestamp']
            # Find the earliest IA whose date is already passed
            locked_ia_dates = [ia_date for ia_date in ia_dates.values() if ia_date and datetime.utcnow() > ia_date]
            if locked_ia_dates:
                earliest_locked = min(locked_ia_dates)
                if session_time < earliest_locked:
                    flash("Attendance for sessions before the completed IA date cannot be modified.", "error")
                    return redirect(url_for('attendance_overview'))


            # Fetch attendance data for the selected session
            record = attendance_db.find_one({
                "class": selected_class,
                "subject": selected_subject,
                "session_id": session_id
            })

            if record:
                for entry in record['attendance']:
                    student = students.find_one({"student_id": entry['student_id']})
                    attendance_data.append({
                        "student_id": entry['student_id'],
                        "name": student['name'] if student else "Unknown",
                        "present": entry['present']
                    })

    return render_template('attendance_overview.html',
                           classes=classes,
                           subjects=subjects,
                           session_options=session_options,
                           attendance_data=attendance_data,
                           selected_class=selected_class,
                           selected_subject=selected_subject,
                           session_id=session_id)




@app.route('/admin/update-attendance', methods=['POST'])
def update_attendance():
    session_id = request.form['session_id']
    class_name = request.form['class_name']
    subject = request.form['subject']
    student_id = request.form['student_id']
    new_status = request.form['new_status'] == 'true'  # Converts "true"/"false" to boolean

    result = attendance_db.update_one(
        {
            "session_id": session_id,
            "class": class_name,
            "subject": subject,
            "attendance.student_id": student_id
        },
        {
            "$set": {
                "attendance.$.present": new_status
            }
        }
    )

    if result.modified_count > 0:
        status_text = "present" if new_status else "absent"
        flash(f"Student marked as {status_text} successfully.", "success")
    else:
        flash("Failed to update attendance.", "error")

    return redirect(url_for('attendance_overview'))


@app.route('/admin/update-face-data', methods=['GET', 'POST'])
def update_face_data():
    if request.method == 'POST':
        role = request.form['role']
        person_id = request.form['person_id']

        # Load user details only
        if role == 'student':
            user = students.find_one({"student_id": person_id})
        else:
            user = teachers.find_one({"teacher_id": person_id})

        if not user:
            flash("User not found.", "error")
            return redirect(url_for('update_face_data'))

        user_data = {
            "role": role,
            "person_id": person_id,
            "name": user.get("name", "N/A"),
            "email": user.get("email", "N/A"),
            "extra": user.get("branch") if role == 'student' else user.get("department", "N/A")
        }

        return render_template('manage_face_data.html', user_data=user_data)

    # GET request
    return render_template('manage_face_data.html', user_data=None)


@app.route('/admin/update-face-data/confirm', methods=['POST'])
def confirm_face_update():
    role = request.form['role']
    person_id = request.form['person_id']

    # Start webcam for face capture
    cam = cv2.VideoCapture(0)
    face_encoding = None

    flash("Please look at the camera to capture your face...", "info")

    while True:
        ret, frame = cam.read()
        if not ret:
            flash("Failed to access the webcam.", "error")
            cam.release()
            cv2.destroyAllWindows()
            return redirect(url_for('update_face_data'))

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        faces = face_recognition.face_locations(rgb_frame)
        encodings = face_recognition.face_encodings(rgb_frame, faces)

        if encodings:
            face_encoding = encodings[0]
            break

        cv2.imshow("Capturing face. Press 'q' to cancel.", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            flash("Face capture cancelled.", "error")
            cam.release()
            cv2.destroyAllWindows()
            return redirect(url_for('update_face_data'))

    cam.release()
    cv2.destroyAllWindows()

    if face_encoding is None:
        flash("No face detected. Try again.", "error")
        return redirect(url_for('update_face_data'))

    update_data = {
        "face_encoding": face_encoding.tolist(),
        "timestamp": datetime.utcnow()
    }

    if role == 'student':
        students.update_one({"student_id": person_id}, {"$set": update_data})
    else:
        teachers.update_one({"teacher_id": person_id}, {"$set": update_data})

    flash("Face data updated successfully.", "success")
    return redirect(url_for('update_face_data'))

@app.route('/admin/update-exam-dates', methods=['GET', 'POST'])
def update_exam_dates():
    if 'admin_name' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('admin_login'))

    # Fetch current exam dates
    exam_doc = exam_dates.find_one()
    
    if request.method == 'POST':
        # Parse new dates from form
        ia1 = request.form.get('IA1')
        ia2 = request.form.get('IA2')
        ia3 = request.form.get('IA3')
        see = request.form.get('SEE')

        # Update or insert the new dates
        new_dates = {
            "IA1": datetime.strptime(ia1, "%Y-%m-%d"),
            "IA2": datetime.strptime(ia2, "%Y-%m-%d"),
            "IA3": datetime.strptime(ia3, "%Y-%m-%d"),
            "SEE": datetime.strptime(see, "%Y-%m-%d")
        }

        if exam_doc:
            exam_dates.update_one({}, {"$set": new_dates})
        else:
            exam_dates.insert_one(new_dates)

        flash("Exam dates updated successfully!", "success")
        return redirect(url_for('update_exam_dates'))

    return render_template("update_exam_dates.html", exam_doc=exam_doc)




def json_serial(obj):
    if isinstance(obj, ObjectId):
        return str(obj)  # Convert ObjectId to string
    raise TypeError("Type not serializable")

if __name__ == '__main__':
    # app.run(port=5001, debug=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
